from django.db import migrations

FORWARD = """
CREATE FUNCTION protect_published_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.is_published THEN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Published versions cannot be deleted'; END IF;
    IF ROW(OLD.product_id, OLD.version_code, OLD.questions_hash, OLD.scoring_hash, OLD.report_template, OLD.is_published)
      IS DISTINCT FROM ROW(NEW.product_id, NEW.version_code, NEW.questions_hash, NEW.scoring_hash, NEW.report_template, NEW.is_published)
      THEN RAISE EXCEPTION 'Published content must be changed in a new version'; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER protect_version BEFORE UPDATE OR DELETE ON quiz_versions FOR EACH ROW EXECUTE FUNCTION protect_published_version();

CREATE FUNCTION protect_version_child() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_version bigint; new_version bigint;
BEGIN
  IF TG_OP <> 'INSERT' THEN old_version := OLD.version_id; END IF;
  IF TG_OP <> 'DELETE' THEN new_version := NEW.version_id; END IF;
  IF EXISTS (SELECT 1 FROM quiz_versions WHERE id IN (old_version, new_version) AND is_published)
    THEN RAISE EXCEPTION 'Published questions and scoring rules are immutable'; END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER protect_question BEFORE INSERT OR UPDATE OR DELETE ON questions FOR EACH ROW EXECUTE FUNCTION protect_version_child();
CREATE TRIGGER protect_scoring BEFORE INSERT OR UPDATE OR DELETE ON scoring_rules FOR EACH ROW EXECUTE FUNCTION protect_version_child();

CREATE FUNCTION protect_question_option() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_question bigint; new_question bigint;
BEGIN
  IF TG_OP <> 'INSERT' THEN old_question := OLD.question_id; END IF;
  IF TG_OP <> 'DELETE' THEN new_question := NEW.question_id; END IF;
  IF EXISTS (SELECT 1 FROM quiz_versions v JOIN questions q ON q.version_id=v.id
             WHERE q.id IN (old_question, new_question) AND v.is_published)
    THEN RAISE EXCEPTION 'Published options are immutable'; END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER protect_option BEFORE INSERT OR UPDATE OR DELETE ON question_options FOR EACH ROW EXECUTE FUNCTION protect_question_option();

CREATE FUNCTION protect_answer() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_attempt uuid; new_attempt uuid; attempt_row record;
BEGIN
  IF TG_OP <> 'INSERT' THEN old_attempt := OLD.attempt_id; END IF;
  IF TG_OP <> 'DELETE' THEN new_attempt := NEW.attempt_id; END IF;
  FOR attempt_row IN SELECT id, status, version_id FROM quiz_attempts
    WHERE id IN (old_attempt, new_attempt) ORDER BY id FOR UPDATE
  LOOP
    IF attempt_row.status <> 'in_progress' THEN RAISE EXCEPTION 'Submitted answers are immutable'; END IF;
    IF TG_OP <> 'DELETE' AND attempt_row.id = new_attempt THEN
      IF NOT EXISTS (SELECT 1 FROM questions q JOIN question_options o ON o.question_id=q.id
          WHERE q.id=NEW.question_id AND o.id=NEW.option_id AND q.version_id=attempt_row.version_id)
        THEN RAISE EXCEPTION 'Answer does not belong to this version'; END IF;
    END IF;
  END LOOP;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER protect_saved_answer BEFORE INSERT OR UPDATE OR DELETE ON answers FOR EACH ROW EXECUTE FUNCTION protect_answer();

CREATE FUNCTION protect_submitted_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'submitted' THEN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Submitted attempts are immutable'; END IF;
    IF ROW(OLD.grant_id, OLD.product_id, OLD.version_id, OLD.status, OLD.submitted_at, OLD.current_question, OLD.revision)
      IS DISTINCT FROM ROW(NEW.grant_id, NEW.product_id, NEW.version_id, NEW.status, NEW.submitted_at, NEW.current_question, NEW.revision)
      THEN RAISE EXCEPTION 'Submitted attempts are immutable'; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER protect_attempt BEFORE UPDATE OR DELETE ON quiz_attempts FOR EACH ROW EXECUTE FUNCTION protect_submitted_attempt();

CREATE FUNCTION protect_order_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF ROW(OLD.product_id, OLD.version_id, OLD.product_title, OLD.amount, OLD.currency, OLD.is_test)
    IS DISTINCT FROM ROW(NEW.product_id, NEW.version_id, NEW.product_title, NEW.amount, NEW.currency, NEW.is_test)
    THEN RAISE EXCEPTION 'Order purchase snapshots are immutable'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER protect_order BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION protect_order_snapshot();
"""

REVERSE = """
DROP TRIGGER protect_order ON orders;
DROP FUNCTION protect_order_snapshot();
DROP TRIGGER protect_attempt ON quiz_attempts;
DROP FUNCTION protect_submitted_attempt();
DROP TRIGGER protect_saved_answer ON answers;
DROP FUNCTION protect_answer();
DROP TRIGGER protect_option ON question_options;
DROP FUNCTION protect_question_option();
DROP TRIGGER protect_scoring ON scoring_rules;
DROP TRIGGER protect_question ON questions;
DROP FUNCTION protect_version_child();
DROP TRIGGER protect_version ON quiz_versions;
DROP FUNCTION protect_published_version();
"""

class Migration(migrations.Migration):
    dependencies = [('operations', '0002_secure_legacy_data')]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
