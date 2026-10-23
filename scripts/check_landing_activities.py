"""Run with `odoo shell -d odoo --no-http < /tmp/check_activities.py`.

All changes are rolled back, including temporary users and photos.
"""
import base64

from odoo.exceptions import AccessError, UserError

checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print('PASS', label)


try:
    Activity = env['edu.landing.activity']
    website = env['website'].search([], limit=1)
    public = env.ref('base.public_user')
    samples = Activity.search([])
    check(len(samples) >= 4, 'four sample slides seeded')
    check(all(samples.mapped('image_1920')), 'samples contain uploaded image data')
    check(all(samples.mapped('event_id')), 'existing photos migrated to events')
    original_events = env['edu.landing.activity.event'].search_count([])
    Activity._organize_activity_events()
    check(env['edu.landing.activity.event'].search_count([]) == original_events, 'event migration is idempotent')
    count = Activity.search_count([])
    Activity._seed_activity_samples()
    check(Activity.search_count([]) == count, 'seed is idempotent')
    samples[0].unlink()
    Activity._seed_activity_samples()
    check(Activity.search_count([]) == count - 1, 'deleted samples do not return')

    designer = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Activity test editor', 'login': '__activity_test_editor__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('website.group_website_designer').id])],
    })
    staff = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Activity test reader', 'login': '__activity_test_reader__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id])],
    })
    Activity.search([]).write({'is_published': False})
    event = env['edu.landing.activity.event'].with_user(designer).create({'name': 'Event test 20/10'})
    image = samples.exists()[0].image_1920
    first = Activity.with_user(designer).create({
        'name': 'First slide', 'sequence': 20, 'image_1920': image,
        'event_id': event.id,
        'is_published': True, 'website_id': website.id,
    })
    second = Activity.with_user(designer).create({
        'name': 'Second slide', 'sequence': 10, 'image_1920': image,
        'event_id': event.id,
        'is_published': True,
    })
    draft = Activity.with_user(designer).create({'name': 'Draft', 'image_1920': image, 'event_id': event.id})
    check(event.image_count == 3 and event.highlight_count == 2, 'event counts stored and highlighted photos')
    visible = website.with_user(public)._get_landing_activities()
    check(visible.ids == [second.id, first.id], 'public slides follow sequence and exclude drafts')
    check(draft.with_user(designer).read(['name'])[0]['name'] == 'Draft', 'editor can read drafts')
    for user, label in [(public, 'public'), (staff, 'internal reader')]:
        try:
            draft.with_user(user).read(['image_1920'])
        except AccessError:
            check(True, '%s cannot read unpublished photos' % label)
        else:
            raise AssertionError('%s read unpublished photo' % label)
        try:
            first.with_user(user).write({'name': 'Forbidden'})
        except AccessError:
            check(True, '%s cannot change photos' % label)
        else:
            raise AssertionError('%s changed a photo' % label)

    other_website = env['website'].create({'name': 'Activity test other website'})
    foreign = Activity.create({
        'name': 'Other website', 'image_1920': image,
        'event_id': event.id,
        'website_id': other_website.id, 'is_published': True,
    })
    check(foreign not in website._get_landing_activities(), 'photos are scoped to the website')
    second.with_user(designer).write({'is_published': False})
    check(website.with_user(public)._get_landing_activities().ids == [first.id], 'hide leaves one visible slide')
    first.with_user(designer).unlink()
    check(not website.with_user(public)._get_landing_activities(), 'delete leaves an empty slideshow safely')

    attachments = env['ir.attachment'].with_user(designer).create([
        {'name': 'Photo A.jpg', 'datas': image, 'mimetype': 'image/jpeg'},
        {'name': 'Photo B.jpg', 'datas': image, 'mimetype': 'image/jpeg'},
    ])
    wizard = env['edu.landing.activity.upload'].with_user(designer).create({
        'event_id': event.id, 'attachment_ids': [(6, 0, attachments.ids)],
    })
    before_ids = event.image_ids.ids
    wizard.action_upload()
    uploads = event.image_ids.filtered(lambda photo: photo.id not in before_ids)
    check(len(uploads) == 2, 'batch upload creates both event photos')
    check(not any(uploads.mapped('is_published')), 'uploaded photos are not highlighted by default')
    check(uploads.mapped('name') == ['Photo A', 'Photo B'], 'upload derives image titles from filenames')
    check(not website.with_user(public)._get_landing_activities(), 'stored uploads remain off the website')
    uploads[0].with_user(designer).write({'is_published': True})
    check(website.with_user(public)._get_landing_activities().ids == uploads[0].ids, 'highlight adds selected photo to slideshow')
    event.write({'active': False})
    check(not website.with_user(public)._get_landing_activities(), 'archived events hide their highlights')
    try:
        uploads[0].with_user(public).read(['image_1920'])
    except AccessError:
        check(True, 'archived event photo cannot be read publicly')
    else:
        raise AssertionError('archived event photo exposed')
    event.write({'active': True})
    check(website.with_user(public)._get_landing_activities().ids == uploads[0].ids, 'restoring event restores highlighted photo')

    invalid = env['ir.attachment'].with_user(designer).create({
        'name': 'note.txt', 'mimetype': 'text/plain', 'datas': base64.b64encode(b'not a photo'),
    })
    bad_wizard = env['edu.landing.activity.upload'].with_user(designer).create({
        'event_id': event.id, 'attachment_ids': [(6, 0, attachments.ids + invalid.ids)],
    })
    photo_count = len(event.image_ids)
    try:
        bad_wizard.action_upload()
    except UserError:
        check(len(event.image_ids) == photo_count, 'invalid batch rejected without creating partial album')
    else:
        raise AssertionError('non-image upload accepted')
    event_photos = event.image_ids
    event.with_user(designer).unlink()
    check(not event_photos.exists(), 'deleting an event removes its contained photos')
    print('TOTAL %s / %s' % (checks, checks))
finally:
    env.cr.rollback()
