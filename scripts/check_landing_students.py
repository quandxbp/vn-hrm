"""Odoo shell regression checks; all records and changes are rolled back."""
from odoo.exceptions import AccessError

checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print('PASS', label)


try:
    Student = env['edu.landing.student']
    website = env['website'].search([], limit=1)
    public = env.ref('base.public_user')
    samples = Student.search([])
    check(len(samples) >= 4 and all(samples.mapped('image_1920')), 'four sample cards have editable image data')
    before = len(samples)
    Student._seed_student_samples()
    check(Student.search_count([]) == before, 'seed does not duplicate existing students')
    samples[0].unlink()
    Student._seed_student_samples()
    check(Student.search_count([]) == before - 1, 'deleted samples are not recreated')
    image = samples.exists()[0].image_1920
    Student.search([]).write({'is_published': False})
    editor = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Showcase test editor', 'login': '__showcase_test_editor__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('website.group_website_designer').id])],
    })
    reader = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Showcase test reader', 'login': '__showcase_test_reader__',
        'groups_id': [(6, 0, [env.ref('base.group_user').id])],
    })
    first = Student.with_user(editor).create({
        'name': 'First student', 'image_1920': image, 'sequence': 20,
        'category': 'sat', 'score': '1520', 'website_id': website.id, 'is_published': True,
    })
    second = Student.with_user(editor).create({
        'name': 'Second student', 'image_1920': image, 'sequence': 10,
        'category': 'cambridge', 'exam_label': 'Flyers', 'score': '15/15', 'is_published': True,
    })
    draft = Student.with_user(editor).create({'name': 'Draft', 'image_1920': image})
    check(not draft.is_published, 'new students stay hidden until published')
    check(first.display_label == 'SAT', 'badge falls back to the selected category')
    check(second.display_label == 'Flyers' and second.score == '15/15', 'custom exam labels and nonnumeric scores supported')
    check(website.with_user(public)._get_landing_students().ids == [second.id, first.id], 'public selection excludes drafts and respects ordering')
    check(draft.with_user(editor).read(['name'])[0]['name'] == 'Draft', 'editor can manage drafts')
    for user, label in [(public, 'public'), (reader, 'internal reader')]:
        try:
            draft.with_user(user).read(['image_1920'])
        except AccessError:
            check(True, '%s cannot read unpublished photos' % label)
        else:
            raise AssertionError('%s accessed a draft' % label)
        try:
            first.with_user(user).write({'school': 'Forbidden'})
        except AccessError:
            check(True, '%s cannot edit website student records' % label)
        else:
            raise AssertionError('%s modified a student' % label)
    other_website = env['website'].create({'name': 'Student showcase test website'})
    foreign = Student.create({
        'name': 'Foreign student', 'image_1920': image,
        'is_published': True, 'website_id': other_website.id,
    })
    check(foreign not in website._get_landing_students(), 'selection is scoped to the website')
    second.with_user(editor).write({'is_published': False})
    check(website.with_user(public)._get_landing_students().ids == first.ids, 'unpublish removes a card from the website')
    first.with_user(editor).unlink()
    check(not website.with_user(public)._get_landing_students(), 'empty section safely returns no records')
    print('TOTAL %s / %s' % (checks, checks))
finally:
    env.cr.rollback()
