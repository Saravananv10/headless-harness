# Client

This directory contains the React frontend for the full-stack application.

## Technologies Used

- **React**: JavaScript library for building user interfaces
- **React Router**: For navigation between pages
- **Axios**: HTTP client for API requests
- **Tailwind CSS**: Utility-first CSS framework
- **React Hooks**: For state and side effects management

## Project Structure

```
client/
├── public/          # Static assets
└── src/             # Source code
    ├── components/  # Reusable UI components
    ├── pages/       # Page components
    ├── services/    # API service layer
    ├── context/     # React context providers
    └── App.js       # Main application component
```

## Setup Instructions

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file (if needed):
```bash
cp .env.example .env
```

3. Start the development server:
```bash
npm start
```

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm run build` - Builds the app for production
- `npm test` - Launches the test runner
- `npm run eject` - Ejects from create-react-app

## Components

### Header
Navigation bar with links to different sections of the app.

### Pages
- Home: Landing page with app overview
- Login: User authentication form
- Register: User registration form
- Profile: User profile management
- Resources: List of resources with CRUD operations

## Styling

The application uses Tailwind CSS for styling, providing a responsive design that works on all device sizes.

## API Integration

The application communicates with the backend through Axios HTTP client configured with:
- Base URL pointing to the backend API
- Authorization headers with JWT tokens
- Error handling for failed requests