# User Authentication System

The LegalAI Doc Assistant features a secure, JWT-based authentication system to ensure data isolation and security for all users.

## Key Features

- **Email & Password Authentication**: Secure registration and login using hashed passwords (bcrypt).
- **Security Questions**: Additional layer of security for password recovery using pre-defined secret questions.
- **JWT Session Management**: Stateless authentication using JSON Web Tokens (JWT).
- **"Remember Me" Functionality**:
    - **Session Storage**: Default behavior; clears auth tokens when the browser tab is closed.
    - **Local Storage**: Persistent sessions; keeps the user logged in across browser restarts if selected.
- **Data Isolation**: Each user's documents and chat history are strictly scoped to their unique User ID.

## Security Implementation

### Backend
- **Bcrypt**: Used for hashing user passwords and security answers before storage.
- **JWT (PyJWT)**: Generates secure access tokens upon successful login.
- **Dependency Injection**: FastAPI dependencies verify tokens on every protected route.

### Frontend
- **Dual-Storage Logic**: Intelligent switching between `localStorage` and `sessionStorage` based on user preference.
- **Protected Routes**: Automatic redirection to the login page if an unauthenticated user tries to access the dashboard.
- **Sensitive Data Handling**: Clear logout mechanism that wipes all local and session-based auth data.

## User Flows

### Registration
1. User enters name, email, and password.
2. User selects a security question and provides an answer.
3. System hashes the password and answer, then redirects to the dashboard.

### Login
1. User enters email and password.
2. User can optionally check "Remember Me".
3. System validates credentials and stores the JWT in the appropriate storage.

### Password Reset
1. User enters their email.
2. System retrieves the associated security question.
3. User provides the correct answer and a new password to regain access.
