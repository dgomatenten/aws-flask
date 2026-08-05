-- Creates the users table used by the Flask auth app.
-- Note: "user" is a PostgreSQL keyword, so this project uses "users".

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username);
