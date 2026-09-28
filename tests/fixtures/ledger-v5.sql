BEGIN TRANSACTION;
CREATE TABLE attempt_context (
                    attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
                    engineer_ids_json TEXT NOT NULL, content_fingerprint TEXT NOT NULL
                );
INSERT INTO "attempt_context" VALUES('historical-attempt','[]','e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
CREATE TABLE attempts (
                    attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    attempt_no INTEGER NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
                    spec_revision INTEGER NOT NULL, changed_files_json TEXT NOT NULL,
                    checks_json TEXT NOT NULL, summary TEXT NOT NULL, state TEXT NOT NULL,
                    created_at INTEGER NOT NULL, UNIQUE(task_id, attempt_no)
                );
INSERT INTO "attempts" VALUES('historical-attempt','e3f4267a3b0ad862-T001',1,'engineer','engineer',1,'[]','[]','historical attempt','submitted',1790583392);
CREATE TABLE dispatches (
                    operation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), stable_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL, route_json TEXT NOT NULL, state TEXT NOT NULL,
                    native_task_id TEXT, effective_route_json TEXT NOT NULL DEFAULT '{}',
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
CREATE TABLE events (
                    event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    operation_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
INSERT INTO "events" VALUES('c9d1577a-379a-4899-8797-483b4ea7390e','e3f4267a3b0ad862','9a7f4004-5658-4c1e-aa31-f06ab27703b8','project_initialized','{"board_slug":"sdd-history","limits":{"estimated_runtime_seconds":300,"max_native_retries":3,"max_provider_recoveries":2,"max_repairs":2,"max_runtime_seconds":3600,"max_total_runtime_seconds":3600,"max_workers":3},"mode":"bugfix"}',1790583392);
INSERT INTO "events" VALUES('ef07c02c-07db-41db-9b8f-19c42ba6fb5b','e3f4267a3b0ad862','e3f4267a3b0ad862:closed','project_closed','{"stage":"accepted"}',1790583392);
INSERT INTO "events" VALUES('d3de3d0e-db3b-40aa-937e-b07bb24adb27','9377914c4ec818b2','8059385b-a3bb-4bce-bbce-0d1b9d4efb22','project_initialized','{"board_slug":"sdd-active","limits":{"estimated_runtime_seconds":300,"max_native_retries":3,"max_provider_recoveries":2,"max_repairs":2,"max_runtime_seconds":3600,"max_total_runtime_seconds":3600,"max_workers":3},"mode":"bugfix"}',1790583392);
INSERT INTO "events" VALUES('88735a6e-7772-4bbe-90d2-ed543409bacd','9377914c4ec818b2','ownership-v5','ownership_acquired','{"files":["app.py"],"owner":"engineer","task_id":"9377914c4ec818b2-T001"}',1790583392);
CREATE TABLE evidence (
                    evidence_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    criterion_id TEXT NOT NULL, kind TEXT NOT NULL, command TEXT NOT NULL,
                    cwd TEXT NOT NULL, exit_status INTEGER NOT NULL, output TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL, created_at INTEGER NOT NULL
                );
INSERT INTO "evidence" VALUES('4011abc8-a761-4974-b7d0-3625b788ef8b','historical-attempt','AC-001','command','python -c pass','__REPOSITORY_ROOT__',0,'historical evidence','historical-fingerprint',1790583392);
CREATE TABLE leases (
                    project_id TEXT PRIMARY KEY REFERENCES projects(project_id), holder TEXT NOT NULL,
                    expires_at INTEGER NOT NULL, acquired_at INTEGER NOT NULL
                );
CREATE TABLE limit_blockers (
                    blocker_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT REFERENCES tasks(task_id), operation_id TEXT NOT NULL,
                    limit_name TEXT NOT NULL, usage INTEGER NOT NULL, cap INTEGER NOT NULL,
                    unblock_condition TEXT NOT NULL, created_at INTEGER NOT NULL, resolved_at INTEGER
                );
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO "metadata" VALUES('schema_version','5');
CREATE TABLE ownership (
                    project_id TEXT NOT NULL REFERENCES projects(project_id), path TEXT NOT NULL,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), owner TEXT NOT NULL,
                    operation_id TEXT NOT NULL, acquired_at INTEGER NOT NULL,
                    PRIMARY KEY(project_id, path)
                );
INSERT INTO "ownership" VALUES('9377914c4ec818b2','app.py','9377914c4ec818b2-T001','engineer','ownership-v5',1790583392);
CREATE TABLE projects (
                    project_id TEXT PRIMARY KEY, root TEXT NOT NULL UNIQUE,
                    board_slug TEXT NOT NULL, stage TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0,
                    limits_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
INSERT INTO "projects" VALUES('e3f4267a3b0ad862','__REPOSITORY_ROOT__#closed-e3f4267a3b0ad862-1790583392','sdd-history','closed',0,'{"estimated_runtime_seconds":300,"max_native_retries":3,"max_provider_recoveries":2,"max_repairs":2,"max_runtime_seconds":3600,"max_total_runtime_seconds":3600,"max_workers":3}',1790583392,1790583392);
INSERT INTO "projects" VALUES('9377914c4ec818b2','__REPOSITORY_ROOT__','sdd-active','planned',0,'{"estimated_runtime_seconds":300,"max_native_retries":3,"max_provider_recoveries":2,"max_repairs":2,"max_runtime_seconds":3600,"max_total_runtime_seconds":3600,"max_workers":3}',1790583392,1790583392);
CREATE TABLE recovery_events (
                    event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), failure_class TEXT NOT NULL,
                    phase TEXT NOT NULL, code TEXT NOT NULL, state TEXT NOT NULL,
                    route_identity TEXT NOT NULL, decision_json TEXT NOT NULL, created_at INTEGER NOT NULL
                );
CREATE TABLE route_breakers (
                    route_identity TEXT PRIMARY KEY, failure_count INTEGER NOT NULL DEFAULT 0,
                    opened_until INTEGER NOT NULL DEFAULT 0, last_failure_at INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'closed', half_open_claimed INTEGER NOT NULL DEFAULT 0
                );
CREATE TABLE runtime_reservations (
                    operation_id TEXT PRIMARY KEY REFERENCES worker_reservations(operation_id),
                    project_id TEXT NOT NULL REFERENCES projects(project_id), task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    reserved_seconds INTEGER NOT NULL, actual_seconds INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL, started_at INTEGER NOT NULL, completed_at INTEGER
                );
INSERT INTO "runtime_reservations" VALUES('reservation-v5','9377914c4ec818b2','9377914c4ec818b2-T001',300,0,'reserved',1790583392,NULL);
CREATE TABLE specs (
                    spec_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    slug TEXT NOT NULL, revision INTEGER NOT NULL, mode TEXT NOT NULL,
                    request TEXT NOT NULL, content_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                    UNIQUE(project_id, slug, revision)
                );
INSERT INTO "specs" VALUES('3c7c0e25-8398-4825-bcfc-1c7b607874eb','e3f4267a3b0ad862','fix-historical-regression',1,'bugfix','Fix historical regression','{"criteria":[{"id":"AC-001","required":true,"text":"The requested change is implemented in the local repository: Fix historical regression"},{"id":"AC-002","required":true,"text":"The relevant automated verification passes."}],"mode":"bugfix","request":"Fix historical regression","tasks":[{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"implementation","parent_key":null,"parent_keys":[],"role":"engineer","stable_key":"T-001","title":"Implement the scoped regression fix"},{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"review","parent_key":"T-001","parent_keys":["T-001"],"role":"reviewer","stable_key":"T-002","title":"Independently review the regression fix"},{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"acceptance","parent_key":"T-002","parent_keys":["T-002"],"role":"qa","stable_key":"T-003","title":"Run acceptance checks and submit evidence"}]}',1790583392);
INSERT INTO "specs" VALUES('ebae35dd-c506-4b36-aed2-883842b4ade6','9377914c4ec818b2','fix-active-regression',1,'bugfix','Fix active regression','{"criteria":[{"id":"AC-001","required":true,"text":"The requested change is implemented in the local repository: Fix active regression"},{"id":"AC-002","required":true,"text":"The relevant automated verification passes."}],"mode":"bugfix","request":"Fix active regression","tasks":[{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"implementation","parent_key":null,"parent_keys":[],"role":"engineer","stable_key":"T-001","title":"Implement the scoped regression fix"},{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"review","parent_key":"T-001","parent_keys":["T-001"],"role":"reviewer","stable_key":"T-002","title":"Independently review the regression fix"},{"difficulty":{"calculated_tier":"med","dimensions":{"consequence":"med","coupling":"med","scope":"med","uncertainty":"med","verification":"med"},"override":null,"policy_version":1,"rationale":"Repository dimensions unassessed; defaulting to med pending inspection.","tier":"med","unassessed":["scope","uncertainty","coupling","consequence","verification"]},"kind":"acceptance","parent_key":"T-002","parent_keys":["T-002"],"role":"qa","stable_key":"T-003","title":"Run acceptance checks and submit evidence"}]}',1790583392);
CREATE TABLE task_budgets (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), repair_cycles INTEGER NOT NULL DEFAULT 0,
                    provider_recoveries INTEGER NOT NULL DEFAULT 0, native_launches INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                );
CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    stable_key TEXT NOT NULL, title TEXT NOT NULL, role TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, spec_revision INTEGER NOT NULL, native_task_id TEXT,
                    parent_key TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(project_id, stable_key)
                );
INSERT INTO "tasks" VALUES('e3f4267a3b0ad862-T001','e3f4267a3b0ad862','T-001','Implement the scoped regression fix','engineer','implementation','review',1,NULL,NULL,1790583392,1790583392);
INSERT INTO "tasks" VALUES('e3f4267a3b0ad862-T002','e3f4267a3b0ad862','T-002','Independently review the regression fix','reviewer','review','planned',1,NULL,'T-001',1790583392,1790583392);
INSERT INTO "tasks" VALUES('e3f4267a3b0ad862-T003','e3f4267a3b0ad862','T-003','Run acceptance checks and submit evidence','qa','acceptance','planned',1,NULL,'T-002',1790583392,1790583392);
INSERT INTO "tasks" VALUES('9377914c4ec818b2-T001','9377914c4ec818b2','T-001','Implement the scoped regression fix','engineer','implementation','queued',1,'native-v5',NULL,1790583392,1790583392);
INSERT INTO "tasks" VALUES('9377914c4ec818b2-T002','9377914c4ec818b2','T-002','Independently review the regression fix','reviewer','review','planned',1,NULL,'T-001',1790583392,1790583392);
INSERT INTO "tasks" VALUES('9377914c4ec818b2-T003','9377914c4ec818b2','T-003','Run acceptance checks and submit evidence','qa','acceptance','planned',1,NULL,'T-002',1790583392,1790583392);
CREATE TABLE worker_reservations (
                    operation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), holder TEXT NOT NULL,
                    state TEXT NOT NULL, reserved_seconds INTEGER NOT NULL,
                    reserved_at INTEGER NOT NULL, released_at INTEGER
                );
INSERT INTO "worker_reservations" VALUES('reservation-v5','9377914c4ec818b2','9377914c4ec818b2-T001','engineer','reserved',300,1790583392,NULL);
CREATE TRIGGER context_immutable_update
                    BEFORE UPDATE ON attempt_context BEGIN SELECT RAISE(ABORT, 'attempt context is immutable'); END;
CREATE TRIGGER context_immutable_delete
                    BEFORE DELETE ON attempt_context BEGIN SELECT RAISE(ABORT, 'attempt context is immutable'); END;
CREATE TRIGGER attempts_immutable_update
                    BEFORE UPDATE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts are immutable'); END;
CREATE TRIGGER attempts_immutable_delete
                    BEFORE DELETE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts are immutable'); END;
CREATE TRIGGER evidence_immutable_update
                    BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
CREATE TRIGGER evidence_immutable_delete
                    BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
COMMIT;
