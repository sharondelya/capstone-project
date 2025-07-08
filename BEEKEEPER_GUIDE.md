# BeeKeeper - Admin Panel Guide

This guide provides instructions for using the BeeKeeper admin panel to manage the Agri Smart application.

## 1. Accessing the Admin Panel

To access the admin panel, navigate to the following URL:

*   **Admin Login**: `http://127.0.0.1:8000/BeeKeeper/`

You will need to use the credentials of a registered administrator to log in.

## 2. Admin Dashboard

The admin dashboard provides a comprehensive overview of the platform's activity. Key metrics displayed include:

*   **Total Users**: A count of all registered clients and businesses.
*   **Monthly Registrations**: A chart showing the number of new client and business sign-ups per month.
*   **Location Statistics**: A breakdown of users by their primary location.
*   **Revenue Statistics**: A summary of the platform's revenue over the last five years.
*   **Subscription Statistics**: A view of the current distribution of subscription plans among businesses.

## 3. Managing Reports

The admin panel allows you to review and take action on reports submitted by users.

### 3.1. Types of Reports

You can manage three types of reports:

*   **Reported Reviews**: Reports against user-submitted reviews.
*   **Reported Clients**: Reports filed against client accounts.
*   **Reported Businesses**: Reports filed against business accounts.

### 3.2. Taking Action on Reports

For each report, you have two primary actions:

*   **Dismiss Report**: If you find a report to be invalid, you can dismiss it, which removes it from the reports list.
*   **Take Action**: Depending on the severity of the report, you can choose to:
    *   **Delete a Review**: Permanently remove an inappropriate review.
    *   **Ban a User**: Temporarily or permanently ban a client or business account.

## 4. User Management

You can manage users directly through the admin panel.

### 4.1. Banning Users

If a user violates the platform's terms of service, you can ban their account.

1.  From the reported clients or businesses page, select the user you wish to ban.
2.  Choose a ban duration (e.g., hours, days, months, permanent).
3.  Confirm the action to ban the user.

### 4.2. Unbanning Users

You can also lift a ban on a user account.

1.  Navigate to the "Unban" page from the admin dashboard.
2.  This page lists all currently banned clients and businesses.
3.  Select the user you wish to unban and confirm the action.

## 5. Managing Subscriptions

The admin panel provides tools to manage business subscriptions.

*   **View Subscriptions**: You can see a list of all active and expired subscriptions.
*   **Update Sponsored Limits**: For each subscription, you can modify the number of sponsored products a business is allowed to have.

This guide covers the main functionalities of the BeeKeeper admin panel. For more detailed information on the application's setup, please refer to the `MAINTENANCE_GUIDE.md`.