# Project: to-do-web-application

## Description
A web application for creating, organizing, tracking, and completing tasks.

## Tasks Checklist

- [ ] **RUN** `backend`
  *Description:* Create the backend directory, navigate into it, and initialize a Node.js project with default settings. This command will be executed from the project root.

- [ ] **MODIFY** `backend/package.json`
  *Description:* Modify the `package.json` file in the backend directory. Add necessary dependencies: `express` for the web framework, `pg` for PostgreSQL client, `dotenv` for environment variables, `bcryptjs` for password hashing, `jsonwebtoken` for authentication tokens, and `cors` for cross-origin resource sharing. Also, add a `start` script to run `node server.js`.

- [ ] **RUN** `backend`
  *Description:* Install the backend dependencies listed in `backend/package.json`. This command will be executed from the 'backend' directory.

- [ ] **CREATE** `backend/server.js`
  *Description:* Create the main entry point for the backend server. This file will load environment variables using `dotenv`, import the Express application from `src/app.js`, and start the server on the configured `PORT` (defaulting to 3001). It should log a message indicating the server is running.

- [ ] **CREATE** `backend/.env`
  *Description:* Create the environment variables file for the backend. Define `PORT=3001` for the server, `DB_USER=todo_user`, `DB_HOST=localhost`, `DB_NAME=todo_db`, `DB_PASSWORD=your_strong_password`, `DB_PORT=5432` for PostgreSQL connection, and `JWT_SECRET=supersecretjwtkey` for signing authentication tokens. These values should be replaced with actual database credentials and a strong, unique secret.

- [ ] **CREATE** `backend/.gitignore`
  *Description:* Create a `.gitignore` file for the backend to exclude `node_modules/` and the `.env` file from version control.

- [ ] **CREATE** `backend/src/app.js`
  *Description:* Create the main Express application configuration file. This file will set up middleware for JSON body parsing (`express.json()`) and Cross-Origin Resource Sharing (`cors()`). It will define a basic root route (`/`) and mount the authentication routes (`authRoutes`) under `/api/auth` and task API routes (`taskRoutes`) under `/api/tasks`.

- [ ] **CREATE** `backend/src/config/db.js`
  *Description:* Create the database configuration file. This module will establish a connection pool to PostgreSQL using the `pg` library and environment variables (`DB_USER`, `DB_HOST`, `DB_NAME`, `DB_PASSWORD`, `DB_PORT`). It will export a `query` function that executes SQL queries using the connection pool, handling potential errors.

- [ ] **CREATE** `backend/src/models/init.sql`
  *Description:* Create an SQL script for initializing the database schema. This script will define the `users` table (columns: `id` SERIAL PRIMARY KEY, `email` VARCHAR(255) UNIQUE NOT NULL, `password_hash` VARCHAR(255) NOT NULL, `created_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP) and the `tasks` table (columns: `id` SERIAL PRIMARY KEY, `user_id` INTEGER NOT NULL, `title` VARCHAR(255) NOT NULL, `description` TEXT, `due_date` TIMESTAMP WITH TIME ZONE, `priority` VARCHAR(50) DEFAULT 'medium', `status` VARCHAR(50) DEFAULT 'incomplete', `created_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, `updated_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP). It will include a foreign key constraint on `tasks.user_id` referencing `users.id` and add indexes for `user_id` and `due_date` for performance.

- [ ] **CREATE** `backend/src/models/userModel.js`
  *Description:* Create the user model. This module will contain functions for interacting with the `users` table. Implement `createUser(email, passwordHash)` to insert a new user, `findUserByEmail(email)` to retrieve a user by their email address, and `findUserById(id)` to retrieve a user by their unique ID. All functions should use the `db.query` utility.

- [ ] **CREATE** `backend/src/models/taskModel.js`
  *Description:* Create the task model. This module will contain functions for interacting with the `tasks` table. Implement `createTask(userId, title, description, dueDate, priority, status)` to insert a new task, `getTasksByUserId(userId, filters)` to fetch all tasks for a specific user (with basic support for query parameters like status or priority for filtering), `getTaskById(taskId, userId)` to retrieve a single task, `updateTask(taskId, userId, updates)` to modify task details, and `deleteTask(taskId, userId)` to remove a task. Ensure all operations include `userId` for authorization checks.

- [ ] **CREATE** `backend/src/controllers/authController.js`
  *Description:* Create the authentication controller. This module will implement the logic for user registration and login. `registerUser` will hash the provided password using `bcryptUtils.hashPassword`, create a new user via `userModel.createUser`, and then generate a JWT using `jwtUtils.generateToken` for the new user. `loginUser` will find a user by email, compare the provided password with the stored hash using `bcryptUtils.comparePassword`, and if successful, generate a JWT.

- [ ] **CREATE** `backend/src/controllers/taskController.js`
  *Description:* Create the task controller. This module will implement the logic for task CRUD operations. `createTask` will extract task data from `req.body` and `req.userId` (from auth middleware) and call `taskModel.createTask`. `getTasks` will call `taskModel.getTasksByUserId` with `req.userId` and any query parameters for filtering. `getTaskById`, `updateTask`, and `deleteTask` will extract `taskId` from `req.params` and `userId` from `req.userId`, then call the corresponding `taskModel` functions, ensuring tasks are associated with the authenticated user.

- [ ] **CREATE** `backend/src/routes/authRoutes.js`
  *Description:* Create the authentication routes using `express.Router`. Define POST endpoints for `/register` and `/login`, mapping them to `authController.registerUser` and `authController.loginUser` respectively.

- [ ] **CREATE** `backend/src/routes/taskRoutes.js`
  *Description:* Create the task routes using `express.Router`. Define API endpoints for `/` (GET for `getTasks`, POST for `createTask`) and `/:id` (GET for `getTaskById`, PUT for `updateTask`, DELETE for `deleteTask`). Apply the `authMiddleware.verifyToken` to all task routes to ensure that only authenticated users can access them.

- [ ] **CREATE** `backend/src/middleware/authMiddleware.js`
  *Description:* Create the authentication middleware. This module will contain a `verifyToken` function. It will extract the JWT from the `Authorization` header (Bearer token), verify its authenticity and expiration using `jsonwebtoken` and `process.env.JWT_SECRET`. If valid, it will decode the token, attach the `userId` from the payload to the `req` object (`req.userId`), and call `next()`. If the token is missing or invalid, it will send a 401 Unauthorized response.

- [ ] **CREATE** `backend/src/utils/jwt.js`
  *Description:* Create a utility module for JSON Web Token (JWT) operations. This module will export a `generateToken(payload)` function that signs a JWT using `jsonwebtoken.sign` with the provided payload (e.g., `{ userId: user.id }`) and the `JWT_SECRET` from environment variables. Set an appropriate expiration time (e.g., '1h').

- [ ] **CREATE** `backend/src/utils/bcrypt.js`
  *Description:* Create a utility module for password hashing. This module will export two asynchronous functions: `hashPassword(password)` which uses `bcryptjs.hash` to hash a plain-text password with a specified salt round (e.g., 10), and `comparePassword(password, hash)` which uses `bcryptjs.compare` to verify if a plain-text password matches a given hash.

- [ ] **MODIFY** `package.json`
  *Description:* Modify the frontend `package.json`. Add `react-router-dom` and `axios` to the `dependencies` section. Add `@types/react-router-dom` and `@types/axios` to the `devDependencies` section for TypeScript support.

- [ ] **RUN** `package.json`
  *Description:* Install the newly added frontend dependencies: `react-router-dom`, `axios`, `@types/react-router-dom`, and `@types/axios`.

- [ ] **MODIFY** `src/main.tsx`
  *Description:* Modify `src/main.tsx`. Import `BrowserRouter` from `react-router-dom` and `AuthContextProvider` (to be created). Wrap the `App` component with `BrowserRouter` to enable client-side routing, and then wrap it with `AuthContextProvider` to provide authentication state globally to the application.

- [ ] **MODIFY** `src/App.tsx`
  *Description:* Remove the default Vite/React boilerplate content from `src/App.tsx`. Implement the main application layout using `react-router-dom`'s `Routes` and `Route` components. Import and render the `Navbar` component. Define public routes for `/login` (using the `Login` component) and `/register` (using the `Register` component). Define a private route for `/dashboard` (using the `Dashboard` component), protected by a `PrivateRoute` component. Add a catch-all route to redirect authenticated users to `/dashboard` and unauthenticated users to `/login`.

- [ ] **CREATE** `src/context/AuthContext.tsx`
  *Description:* Create a React Context (`AuthContext`) for managing user authentication state. Define interfaces for `User` (e.g., `{ id: string; email: string; }`) and `AuthContextType` (containing `user`, `token`, `login`, `register`, `logout`). Implement `AuthContextProvider` to manage `user` and `token` state using `useState` and `useEffect` for persistence in `localStorage`. The `login` and `register` functions will call the `auth` API service, store the received token and user data, and update the context state. The `logout` function will clear the state and `localStorage`.

- [ ] **CREATE** `src/components/auth/Login.tsx`
  *Description:* Create the Login component. This component will render a form with input fields for email and password. Use `useState` to manage form input values. On form submission, it will use the `AuthContext`'s `login` function to authenticate the user. Upon successful login, use `useNavigate` from `react-router-dom` to redirect the user to the `/dashboard` page. Include basic client-side validation and error display.

- [ ] **CREATE** `src/components/auth/Register.tsx`
  *Description:* Create the Register component. This component will render a form with input fields for email and password. Use `useState` to manage form input values. On form submission, it will use the `AuthContext`'s `register` function to create a new user account. Upon successful registration, use `useNavigate` from `react-router-dom` to redirect the user to the `/login` page. Include basic client-side validation and error display.

- [ ] **CREATE** `src/components/common/Navbar.tsx`
  *Description:* Create a responsive navigation bar component. It will display the application title ('To-Do App'). Use `useContext(AuthContext)` to conditionally render navigation links: 'Login' and 'Register' if the user is not authenticated, or 'Dashboard' and a 'Logout' button if the user is authenticated. The 'Logout' button will call `authContext.logout()` to clear the user session.

- [ ] **CREATE** `src/components/tasks/Dashboard.tsx`
  *Description:* Create the Dashboard component. This will be the main authenticated view. It should fetch the user's tasks using the `tasks` API service on component mount and whenever tasks need to be refreshed. It will display a `TaskForm` component for creating new tasks. It will render a `TaskList` component, passing the fetched tasks and callback functions for handling task updates (e.g., marking complete) and deletions. Implement basic filtering (e.g., 'All', 'Completed', 'Pending') and sorting options (e.g., 'Due Date', 'Priority') using local state and pass these as props to `TaskList`.

- [ ] **CREATE** `src/components/tasks/TaskList.tsx`
  *Description:* Create the TaskList component. This component will receive an array of `tasks` as props, along with `onUpdateTask` and `onDeleteTask` callback functions. It will map over the `tasks` array and render a `TaskItem` component for each task. It should also include UI elements for filtering and sorting tasks (e.g., dropdowns, buttons) that, when interacted with, trigger state updates in the parent `Dashboard` component.

- [ ] **CREATE** `src/components/tasks/TaskItem.tsx`
  *Description:* Create the TaskItem component. This component will display a single task's details, including its title, description, due date, priority, and status. It will receive a `task` object as props, along with `onUpdate` and `onDelete` callback functions. It should include interactive elements such as a checkbox to mark the task as complete/incomplete, an 'Edit' button (which might trigger an edit mode or open a `TaskForm` for editing), and a 'Delete' button. These actions will call the respective `onUpdate` or `onDelete` callbacks with the task's ID and updated data.

- [ ] **CREATE** `src/components/tasks/TaskForm.tsx`
  *Description:* Create the TaskForm component. This component will render a form for creating a new task or editing an existing one. It will include input fields for `title`, `description`, `due_date` (e.g., an HTML date input), `priority` (a dropdown with 'Low', 'Medium', 'High' options), and `status` (a dropdown with 'Incomplete', 'In Progress', 'Completed' options). Use `useState` to manage form input values. If an `initialTask` prop is provided, the form fields should be pre-filled for editing. On form submission, it will call `tasksApi.createTask` or `tasksApi.updateTask` and then invoke an `onTaskCreated` or `onTaskUpdated` callback function passed from the parent component. Include basic client-side form validation.

- [ ] **CREATE** `src/components/routing/PrivateRoute.tsx`
  *Description:* Create a PrivateRoute component. This component will check if a user is authenticated by consuming the `AuthContext`. If `authContext.token` is present, it will render its `children` (the protected component). Otherwise, it will use the `Navigate` component from `react-router-dom` to redirect the unauthenticated user to the `/login` page.

- [ ] **CREATE** `src/api/auth.ts`
  *Description:* Create an API service for authentication. This module will contain asynchronous functions `register(email, password)` and `login(email, password)`. These functions will use `axios` to make POST requests to the backend authentication endpoints (e.g., `API_BASE_URL/auth/register` and `API_BASE_URL/auth/login`). They should handle potential errors and return the response data, typically including a JWT token and user information on success.

- [ ] **CREATE** `src/api/tasks.ts`
  *Description:* Create an API service for tasks. This module will contain asynchronous functions for `createTask(taskData)`, `getTasks(filters?)`, `getTaskById(id)`, `updateTask(id, updates)`, and `deleteTask(id)`. These functions will use `axios` to make authenticated HTTP requests to the backend task endpoints (e.g., `API_BASE_URL/tasks` and `API_BASE_URL/tasks/:id`). Ensure `axios` is configured to include the JWT token (retrieved from `localStorage`) in the `Authorization` header for all requests to protected routes.

- [ ] **CREATE** `src/utils/constants.ts`
  *Description:* Create a utility file for application constants. Define `API_BASE_URL` as `http://localhost:3001/api`. This constant will be used by the frontend API services (`auth.ts`, `tasks.ts`) to target the backend server.

- [ ] **MODIFY** `src/index.css`
  *Description:* Replace the default Vite global styles in `src/index.css` with basic application-wide CSS. Include a CSS reset (`* { margin: 0; padding: 0; box-sizing: border-box; }`), define a primary font (e.g., 'Inter', sans-serif), and set up basic CSS custom properties (variables) for colors (e.g., `--primary-color`, `--text-color`, `--background-color`). Ensure a clean and consistent base for styling all components.

- [ ] **MODIFY** `src/App.css`
  *Description:* Remove the default Vite `App.css` content. Add basic layout styles for the main application container (e.g., `display: flex; flex-direction: column; min-height: 100vh;`), navigation, and content areas. Include responsive design considerations using media queries for desktop and mobile views. Define general styles for common UI elements like buttons, forms, input fields, and card-like containers to ensure a consistent look and feel across the application.

