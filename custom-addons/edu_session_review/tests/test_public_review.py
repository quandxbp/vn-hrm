import json
from lxml import html
from odoo.tests import TransactionCase, HttpCase, tagged


def fixtures(env):
    env.ref('edu_video.config_default').sudo().write({'auto_upload': False, 'processing_enabled': False, 'review_auto': False})
    week=env['edu.week'].create({'number': 99884, 'date_from': '2052-01-01', 'date_to': '2052-01-07'})
    teacher=env['edu.teacher'].create({'name': 'Review Portal Teacher'})
    other=env['edu.teacher'].create({'name': 'Other Review Teacher'})
    session=env['edu.session'].create({'date':'2052-01-02','teacher_id':teacher.id,
        'google_drive_url':'https://drive.google.com/file/d/portal_review_source/view',
        'youtube_url':'https://youtu.be/aBcDeFgH123'})
    review=env['edu.session.review'].create({'session_id':session.id,'model_name':'test-only',
        'state':'done','source_signature':session._review_signature(),
        'summary':'PRIVATE_REVIEW_SENTINEL <img src=x onerror=alert(1)>',
        'lesson_content':'CONTENT_SENTINEL','strengths':'STRENGTHS_SENTINEL','improvements':'IMPROVEMENTS_SENTINEL',
        'score_available':True,'score_total':7.5,'score_content':2,'score_instruction':2,
        'score_interaction':1.5,'score_management':2,'score_details':'SCORING_SENTINEL',
        'sufficient_data':True,'total_minutes':30,'teaching_minutes':25,'teaching_percent':83.3,
        'teaching_started_at':'Part 1 01:30','timing_note':'TIMING_SENTINEL',
        'timing_details':'SEGMENTS_SENTINEL','interaction_comment':'INTERACTION_SENTINEL',
        'quality_note':'QUALITY_SENTINEL'})
    return week,teacher,other,session,review


@tagged('post_install','-at_install')
class TestPrivateTeacherReview(TransactionCase):
    def setUp(self):
        super().setUp()
        self.week,self.teacher,self.other,self.session,self.review=fixtures(self.env)
        self.page=self.env['edu.public.schedule'].with_user(self.env.ref('base.public_user'))

    def test_owner_receives_complete_allowlisted_report(self):
        status,data=self.page._teacher_session_review(self.teacher.schedule_edit_token,self.session.id)
        self.assertEqual(status,200)
        report=data['report']
        self.assertEqual(report['score_total'],7.5)
        for key in ('summary','lesson_content','strengths','improvements','score_details','timing_note','timing_details','interaction_comment','quality_note'):
            self.assertTrue(report[key])
        self.assertEqual(len(report['scores']),4)
        self.assertFalse(data['stale'])
        for field in ('result_json','error','requested_by','review_api_key','gemini_uri','source_signature'):
            self.assertNotIn(field,report)

    def test_invalid_foreign_rotated_and_inactive_tokens_cannot_read(self):
        for token,sid,expected in [('',self.session.id,403),(self.other.schedule_edit_token,self.session.id,404),
                                   (self.teacher.schedule_edit_token,-1,404),(self.teacher.schedule_edit_token,True,404)]:
            status,data=self.page._teacher_session_review(token,sid)
            self.assertEqual(status,expected)
            self.assertNotIn('PRIVATE_REVIEW_SENTINEL',json.dumps(data))
        old=self.teacher.schedule_edit_token
        self.teacher.sudo().write({'schedule_edit_token':'x'*43})
        self.assertEqual(self.page._teacher_session_review(old,self.session.id)[0],403)
        self.teacher.active=False
        self.assertEqual(self.page._teacher_session_review('x'*43,self.session.id)[0],403)

    def test_latest_pending_and_failed_reviews_hide_internal_errors(self):
        latest=self.review.copy({'state':'analyzing','error':'INTERNAL_SECRET_SENTINEL'})
        status,data=self.page._teacher_session_review(self.teacher.schedule_edit_token,self.session.id)
        self.assertEqual(data['state'],'analyzing')
        self.assertNotIn('report',data)
        latest.state='failed'
        self.assertNotIn('INTERNAL_SECRET_SENTINEL',json.dumps(self.page._teacher_session_review(self.teacher.schedule_edit_token,self.session.id)))

    def test_public_projection_contains_no_review_content(self):
        public=self.page._get_values(self.teacher.name,str(self.week.number))
        self.assertFalse(public['review_enabled'])
        self.assertNotIn('PRIVATE_REVIEW_SENTINEL',str(public))
        editor=self.page._get_values(self.teacher.name,str(self.week.number),editor=self.teacher)
        self.assertTrue(editor['review_enabled'])
        self.assertNotIn('PRIVATE_REVIEW_SENTINEL',str(editor))

    def test_stale_report_is_explicitly_marked(self):
        self.session.google_drive_url='https://drive.google.com/file/d/portal_review_changed/view'
        status,data=self.page._teacher_session_review(self.teacher.schedule_edit_token,self.session.id)
        self.assertEqual(status,200)
        self.assertTrue(data['stale'])

    def test_no_report_does_not_queue_an_analysis(self):
        self.review.unlink()
        before=self.env['edu.session.review'].search_count([])
        status,data=self.page._teacher_session_review(self.teacher.schedule_edit_token,self.session.id)
        self.assertEqual(status,200)
        self.assertEqual(data['state'],'missing')
        self.assertEqual(self.env['edu.session.review'].search_count([]),before)


@tagged('post_install','-at_install')
class TestTeacherReviewHttp(HttpCase):
    def test_private_modal_endpoint_requires_csrf_and_owner_token(self):
        week,teacher,other,session,review=fixtures(self.env)
        self.authenticate(None,None)
        response=self.url_open('/weekly-schedule/edit/'+teacher.schedule_edit_token+'?week='+str(week.number))
        self.assertEqual(response.status_code,200)
        tree=html.fromstring(response.content)
        auth=tree.xpath('//form[@id="session-review-auth"]')[0]
        data={el.get('name'):el.get('value','') for el in auth.xpath('.//input')}
        data['session_id']=str(session.id)
        path='/weekly-schedule/session-review'
        self.assertEqual(self.url_open(path,data={k:v for k,v in data.items() if k!='csrf_token'}).status_code,400)
        response=self.url_open(path,data=data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['report']['score_total'],7.5)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['Referrer-Policy'],'no-referrer')
        data['edit_token']=other.schedule_edit_token
        self.assertEqual(self.url_open(path,data=data).status_code,404)
        data['edit_token']='invalid'
        self.assertEqual(self.url_open(path,data=data).status_code,403)
        public=self.url_open('/weekly-schedule?teacher='+teacher.name+'&week='+str(week.number))
        self.assertNotIn('PRIVATE_REVIEW_SENTINEL',public.text)
        self.assertNotIn('session-review-auth',public.text)
        buttons=html.fromstring(public.content).xpath('//button[@class="session-review-button"]')
        self.assertTrue(buttons and all(b.get('disabled') is not None for b in buttons))
