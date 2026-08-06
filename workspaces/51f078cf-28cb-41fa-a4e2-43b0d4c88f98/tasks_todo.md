# Project: ERP Management System

## Description
An ERP system integrating HR, Finance, Inventory, Sales, Procurement, and Reporting.

## Tasks Checklist

- [ ] **MODIFY** `package.json`
  *Description:* Add `react-router-dom` to the `dependencies` section in `package.json`. This package is essential for client-side routing, enabling navigation between different modules of the ERP system without full page reloads.

- [ ] **RUN** `package.json`
  *Description:* Install the newly added `react-router-dom` dependency.

- [ ] **MODIFY** `vite.config.ts`
  *Description:* Modify `vite.config.ts` to configure the Vite development server. Add a `server` object with `port: 3000` and `host: '0.0.0.0'` to ensure the frontend runs on the specified port and is accessible from all network interfaces, aligning with the project's `run_command`.

- [ ] **MODIFY** `src/index.css`
  *Description:* Replace the entire content of `src/index.css` with global styles for the ERP system. This includes a CSS reset (`* { margin: 0; padding: 0; box-sizing: border-box; }`), defining custom CSS properties for colors (`--primary-color`, `--secondary-color`, `--background-color`, `--text-color`, etc.), basic typography for `body` and headings, and foundational layout styles for the `html` and `body` elements to ensure full height and a consistent font. Also, define a `.container` class for consistent content width and padding, and basic styles for links and buttons. Implement a flexbox layout for the main application structure.

- [ ] **MODIFY** `src/App.css`
  *Description:* Clear all existing boilerplate styles from `src/App.css`. This file will be left empty as global styles are managed in `src/index.css` and component-specific styles will be handled either inline or via CSS modules if needed later.

- [ ] **MODIFY** `src/main.tsx`
  *Description:* Modify `src/main.tsx` to import `BrowserRouter` from `react-router-dom`. Wrap the `<App />` component with `<BrowserRouter>` to enable client-side routing for the entire application. Ensure `StrictMode` is maintained.

- [ ] **MODIFY** `src/App.tsx`
  *Description:* Completely replace the default boilerplate content in `src/App.tsx`. Import `Routes`, `Route`, and `Outlet` from `react-router-dom`, and the `Layout` component, along with all page components (Auth, Dashboard, EmployeeManagement, InventoryManagement, ProcurementManagement, SalesManagement, FinanceManagement, ReportingDashboard). Define the main application routing structure: a route for `/auth` that renders the `Auth` component (for login/registration), without the `Layout`. A parent route for `/` that uses the `Layout` component, containing nested routes for `/` (index route) rendering `Dashboard`, and specific routes for `/employees`, `/inventory`, `/procurement`, `/sales`, `/finance`, and `/reporting` rendering their respective management components. This structure ensures consistent navigation and layout for authenticated users.

- [ ] **CREATE** `src/components/Layout.tsx`
  *Description:* Create `src/components/Layout.tsx`. This functional component will define the main layout of the ERP system. It will import `Navbar` and `Sidebar` components, and `Outlet` from `react-router-dom`. The component will render a `div` with a class like `erp-layout` that contains: a `Navbar` component at the top, and a main content area structured with flexbox, where a `Sidebar` component is on the left and an `Outlet` (for rendering nested route components) is on the right. This ensures a consistent header and sidebar navigation across all authenticated pages.

- [ ] **CREATE** `src/components/Navbar.tsx`
  *Description:* Create `src/components/Navbar.tsx`. This functional component will render the top navigation bar. It will include: a `div` for the ERP system's logo/name (e.g., 'ERP System'), a `div` for user information (e.g., 'Welcome, User!'), and a placeholder 'Logout' button. Apply basic styling to make it a distinct top bar, potentially using flexbox for alignment.

- [ ] **CREATE** `src/components/Sidebar.tsx`
  *Description:* Create `src/components/Sidebar.tsx`. This functional component will render the left-hand navigation menu. It will import `NavLink` from `react-router-dom`. The component will display an unordered list (`ul`) of navigation links for all main ERP modules: Dashboard (`/`), Employee Management (`/employees`), Inventory Management (`/inventory`), Procurement Management (`/procurement`), Sales Management (`/sales`), Finance Management (`/finance`), and Reporting Dashboard (`/reporting`). Each `NavLink` should have an `activeClassName` for styling the currently active link. Apply basic styling to make it a distinct sidebar with vertical navigation.

- [ ] **CREATE** `src/pages/Dashboard.tsx`
  *Description:* Create `src/pages/Dashboard.tsx`. This functional component will serve as the main landing page after login. Initially, it will render a simple `div` containing an `h1` tag with the text 'Dashboard Page Content' and a paragraph with a welcome message.

- [ ] **CREATE** `src/pages/EmployeeManagement.tsx`
  *Description:* Create `src/pages/EmployeeManagement.tsx`. This functional component will be dedicated to managing employee records. Initially, it will render a simple `div` containing an `h1` tag with the text 'Employee Management Page Content'.

- [ ] **CREATE** `src/pages/InventoryManagement.tsx`
  *Description:* Create `src/pages/InventoryManagement.tsx`. This functional component will handle product inventory. Initially, it will render a simple `div` containing an `h1` tag with the text 'Inventory Management Page Content'.

- [ ] **CREATE** `src/pages/ProcurementManagement.tsx`
  *Description:* Create `src/pages/ProcurementManagement.tsx`. This functional component will manage purchasing processes. Initially, it will render a simple `div` containing an `h1` tag with the text 'Procurement Management Page Content'.

- [ ] **CREATE** `src/pages/SalesManagement.tsx`
  *Description:* Create `src/pages/SalesManagement.tsx`. This functional component will manage sales orders. Initially, it will render a simple `div` containing an `h1` tag with the text 'Sales Management Page Content'.

- [ ] **CREATE** `src/pages/FinanceManagement.tsx`
  *Description:* Create `src/pages/FinanceManagement.tsx`. This functional component will cover financial operations. Initially, it will render a simple `div` containing an `h1` tag with the text 'Finance Management Page Content'.

- [ ] **CREATE** `src/pages/ReportingDashboard.tsx`
  *Description:* Create `src/pages/ReportingDashboard.tsx`. This functional component will display various reports and analytics. Initially, it will render a simple `div` containing an `h1` tag with the text 'Reporting Dashboard Page Content'.

- [ ] **CREATE** `src/pages/Auth.tsx`
  *Description:* Create `src/pages/Auth.tsx`. This functional component will handle user authentication (login/registration). Initially, it will render a simple `div` containing an `h1` tag with the text 'Authentication Page Content' and a placeholder login form (e.g., input fields for username/password and a submit button).

