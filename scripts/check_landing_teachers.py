"""Odoo shell checks for website teachers; all changes are rolled back."""
from odoo.exceptions import AccessError

checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print('PASS', label)


try:
    Teacher = env['edu.landing.teacher']
    website = env['website'].search([], limit=1)
    public = env.ref('base.public_user')
    samples = Teacher.search([])
    check(len(samples) >= 4 and all(samples.mapped('image_1920')), 'four editable sample photos exist')
    count = len(samples)
    Teacher._seed_teacher_samples()
    check(Teacher.search_count([]) == count, 'sample seed is idempotent')
    samples[0].unlink()
    Teacher._seed_teacher_samples()
    check(Teacher.search_count([]) == count - 1, 'deleted samples remain deleted')
    image = samples.exists()[0].image_1920
    Teacher.search([]).write({'is_published': False})
    editor = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Teacher showcase editor', 'login': '__teacher_showcase_editor__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('website.group_website_designer').id])],
    })
    reader = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Teacher showcase reader', 'login': '__teacher_showcase_reader__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id])],
    })
    first = Teacher.with_user(editor).create({
        'name': 'Center teacher', 'team': 'center', 'image_1920': image,
        'sequence': 20, 'is_published': True, 'website_id': website.id,
    })
    second = Teacher.with_user(editor).create({
        'name': 'International teacher', 'team': 'international', 'image_1920': image,
        'sequence': 10, 'is_published': True, 'certification': 'TESOL',
    })
    draft = Teacher.with_user(editor).create({'name': 'Draft', 'image_1920': image})
    check(not draft.is_published, 'new profiles are hidden by default')
    visible = website.with_user(public)._get_landing_teachers()
    check(visible.ids == [second.id, first.id], 'public selection respects publication and sequence')
    check(len(visible.filtered(lambda t: t.team == 'center')) == 1 and len(visible.filtered(lambda t: t.team == 'international')) == 1, 'profiles fall into the correct teams')
    first.with_user(editor).write({'team': 'international'})
    check(not website.with_user(public)._get_landing_teachers().filtered(lambda t: t.team == 'center'), 'changing team updates the website grouping')
    check(draft.with_user(editor).read(['name'])[0]['name'] == 'Draft', 'editor can manage unpublished profiles')
    for user, label in [(public, 'public'), (reader, 'internal reader')]:
        try:
            draft.with_user(user).read(['image_1920'])
        except AccessError:
            check(True, '%s cannot read unpublished photos' % label)
        else:
            raise AssertionError('%s accessed unpublished teacher' % label)
        try:
            first.with_user(user).write({'position': 'Forbidden'})
        except AccessError:
            check(True, '%s cannot edit profiles' % label)
        else:
            raise AssertionError('%s changed a profile' % label)
    other_website = env['website'].create({'name': 'Teacher showcase other website'})
    foreign = Teacher.create({'name': 'Other website', 'image_1920': image, 'is_published': True, 'website_id': other_website.id})
    check(foreign not in website._get_landing_teachers(), 'profiles are scoped to the website')
    second.with_user(editor).write({'is_published': False})
    check(website.with_user(public)._get_landing_teachers().ids == first.ids, 'unpublish removes the profile')
    first.with_user(editor).unlink()
    check(not website.with_user(public)._get_landing_teachers(), 'empty groups return no profiles safely')
    print('TOTAL %s / %s' % (checks, checks))
finally:
    env.cr.rollback()
