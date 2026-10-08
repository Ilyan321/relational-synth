-- Fuzz test cases for table: departments
-- Violation: NULL in NOT NULL column 'department_id'
INSERT INTO departments (department_id, department_name, created_at) VALUES (NULL, 'Diverse encompassing info-mediaries', NULL);
-- Violation: Duplicate value in UNIQUE column 'department_id'
INSERT INTO departments (department_id, department_name, created_at) VALUES (1, 'Streamlined web-enabled strategy', '2025-06-21T04:44:05.991921');
-- Violation: NULL in NOT NULL column 'department_name'
INSERT INTO departments (department_id, department_name, created_at) VALUES (8, NULL, '2025-11-09T20:18:29.104310');
-- Violation: Duplicate value in UNIQUE column 'department_name'
INSERT INTO departments (department_id, department_name, created_at) VALUES (9, 'Reactive uniform algorithm', '2025-03-08T23:33:30.419330');

-- Fuzz test cases for table: students
-- Violation: NULL in NOT NULL column 'student_id'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (NULL, 'Michael', 'Rogers', 'joel51@example.net', 4, '2026-10-04');
-- Violation: Duplicate value in UNIQUE column 'student_id'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (1, 'Peter', 'Rogers', 'sburke@example.org', 5, '2026-09-02');
-- Violation: NULL in NOT NULL column 'first_name'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (8, NULL, 'Jimenez', 'hgarrett@example.net', 1, '2026-06-11');
-- Violation: NULL in NOT NULL column 'last_name'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (9, 'Dustin', NULL, 'melissastokes@example.org', 3, NULL);
-- Violation: NULL in NOT NULL column 'email'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (10, 'Jonathan', 'Williams', NULL, 4, '2026-04-03');
-- Violation: Duplicate value in UNIQUE column 'email'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (11, 'Megan', 'Johnson', 'edavis@example.net', 1, '2025-11-06');
-- Violation: Orphan Foreign Key reference on 'department_id'
INSERT INTO students (student_id, first_name, last_name, email, department_id, enrollment_date) VALUES (12, 'Craig', 'Ortiz', 'kleinedward@example.net', 99999999, '2026-05-24');
