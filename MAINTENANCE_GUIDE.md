# Agri Smart - Maintenance Guide

This guide provides instructions for setting up and running the Agri Smart application for maintenance and development purposes.

## 1. Prerequisites

Before you begin, ensure you have the following software installed on your system:

*   **Python 3.x**: Download and install from [python.org](https://python.org).
*   **PostgreSQL**: Download and install from [postgresql.org](https://www.postgresql.org/download/).
*   **Git**: Download and install from [git-scm.com](https://git-scm.com/downloads).

## 2. Setup

Follow these steps to set up the project on your local machine:

### 2.1. Clone the Repository

If you haven't already, clone the project repository using Git:

```bash
git clone https://gitlab.com/wgu-gitlab-environment/student-repos/ptchou1/d424-software-engineering-capstone/-/tree/Working?ref_type=heads
cd honeybee-haven-backend
```

### 2.2. Create a Virtual Environment

It is recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 2.3. Install Dependencies

Install the required Python packages using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## 3. Database Configuration

The application uses a PostgreSQL database. Follow these steps to configure it:

### 3.1. Create the Database

1.  Open the PostgreSQL command-line tool (`psql`).
2.  Create a new database named `honeybeehavenschema`:

    ```sql
    CREATE DATABASE honeybeehavenschema;
    ```

3.  You will need a database user with privileges to access this database. You can use the default `postgres` user or create a new one.

### 3.2. Configure Database Connection

The database connection settings are located in the `app.py` file. Open [`app.py`](app.py) and update the `DB_CONFIG` dictionary with your PostgreSQL credentials:

```python
# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'honeybeehavenschema',
    'user': 'your_db_user',
    'password': 'your_db_password'
}
```

### 3.3. Database Schema

The application does not use a migration tool like Alembic or Flask-Migrate. The database schema is implicitly defined by the Db file. First screate a database named honeybeehavenschema then after creating it right click on it and select restore and then select the AgriSmart File and Press ok. After that your Database schema will be loaded automatically.

Or Alternatively, you can just run the Database_initialization.py file after putting your postgresql credentials , it will automatically create the tables for you.

## 4. Running the Application

Once the setup and configuration are complete, you can run the Flask development server:

```bash
flask run
```

Alternatively, you can run the `app.py` file directly:

```bash
python app.py
```

The application will be accessible at `http://127.0.0.1:8000` in your web browser.

## 5. Project Structure

Here is a brief overview of the project's directory structure:

```
.
├── app.py              # Main Flask application file
├── requirements.txt    # Python dependencies
|__Testing/             # Contains all the testing scripts and result
|__Diagrams/            # Contains all the class diagram and design diagram and use case diagram
|__BEEKEEPER_GUIDE.md   # Contains the guide for admin side
|__MAINTENANCE_GUIDE.md # Contains the guide for maintenance
|__Database_initialization.py # Contains the script for creating the tables in the database 
|__USER_GUIDE.md        # Contains the user guide manual
|__AgriSmart            # Database File
├── static/             # Static assets (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
└── templates/          # HTML templates
    ├── beekeeper/      # Admin-related templates
    └── honeybeehaven/  # Main application templates
```

*   **`app.py`**: Contains all the Flask routes and application logic.
*   **`static/`**: Holds static files that are served directly to the client.
*   **`templates/`**: Contains Jinja2 templates for rendering HTML pages.

## 6. Main Application (Agri Smart)

The main application, accessible to clients and businesses, is built as a monolithic Flask application. All core logic is contained within [`app.py`](app.py).

### 6.1. User Roles

The application supports two main user roles:

*   **Client**: Can browse the marketplace, purchase products, write reviews, and manage their orders.
*   **Business**: Can list products (chemicals, machinery, services), manage their inventory, view sales reports, and manage their business profile.

### 6.2. Key Functionalities

*   **Authentication**: User registration and login for both clients and businesses. Passwords are encrypted using `bcrypt`.
*   **Product Management**: Businesses can perform CRUD (Create, Read, Update, Delete) operations on their products.
*   **Marketplace**: A filterable and searchable view of all products for clients.
*   **Shopping Cart**: A persistent shopping cart for clients to add and manage items before purchase.
*   **Checkout and Payments**: Integration with Stripe for processing payments. The application creates a payment intent and confirms the payment on the backend.
*   **Order Management**: Clients can view their order history, and businesses can manage the orders for their products.
*   **Reviews and Ratings**: Clients can submit reviews and ratings for products they have purchased.
*   **Reporting System**: Users can report businesses, clients, or reviews that violate the platform's policies.
*   **Messaging System**: A built-in chat feature for clients and businesses to communicate.
*   **Notifications**: A system to notify users about important events, such as new orders or subscription updates.
*   **Business Subscriptions**: A subscription model for businesses to access premium features like product sponsorship.

## 7. Admin Panel (BeeKeeper)

The application includes an admin panel for site administrators, located under the `/BeeKeeper/` route.

### 6.1. Admin Login

*   **URL**: `http://127.0.0.1:8000/BeeKeeper/`
*   **Credentials**: The application uses a separate `admin2` table for admin users. You will need to add an admin user to this table manually to be able to log in.

### 6.2. Admin Functionalities

The admin panel provides functionalities to:

*   View dashboard with site statistics.
*   Manage user reports (reported businesses, clients, and reviews).
*   View and manage subscriptions.
*   Ban or unban users.
*   View contact form submissions.