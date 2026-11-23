def migrate(cr, version):
    # Rows created by 17.0.1.0.0 are all shadow rows: copy the Gemini report's source and schedule.
    cr.execute("""
        UPDATE edu_session_review_shadow s
           SET mode = COALESCE(s.mode, 'shadow'),
               source_signature = COALESCE(s.source_signature, r.source_signature),
               planned_minutes = COALESCE(s.planned_minutes, r.planned_minutes)
          FROM edu_session_review r
         WHERE r.id = s.review_id
    """)
