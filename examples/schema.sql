-- Database Schema for Student Management System

CREATE TABLE IF NOT EXISTS departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department_id INT REFERENCES departments(department_id) ON DELETE SET NULL,
    enrollment_date DATE DEFAULT CURRENT_DATE
);

INSERT INTO departments (department_name) VALUES ('Computer Science'), ('Data Science');

INSERT INTO students (first_name, last_name, email, department_id) VALUES
('John', 'Doe', 'john.doe@university.edu', 1),
('Jane', 'Smith', 'jane.smith@university.edu', 2);

SELECT s.student_id, s.first_name, s.last_name, d.department_name
FROM students s JOIN departments d ON s.department_id = d.department_id;
