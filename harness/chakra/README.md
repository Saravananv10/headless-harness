# Full-Stack Web Application

A complete full-stack web application built with React frontend, Node.js/Express backend, SQLite database, JWT authentication, and RESTful API endpoints.

## Features

- **Frontend**: React with modern components
- **Backend**: Node.js with Express framework
- **Database**: SQLite with Sequelize ORM
- **Authentication**: JWT-based user authentication
- **API**: RESTful endpoints for all resources
- **Documentation**: Complete setup instructions

## Technologies Used

### Frontend
- React 18+
- React Router
- Axios for HTTP requests
- Tailwind CSS for styling
- React Hooks

### Backend
- Node.js 16+
- Express.js
- SQLite3
- Sequelize ORM
- JWT Authentication
- Bcrypt for password hashing
- Dotenv for environment variables

### Development Tools
- Nodemon for development server
- ESLint for code linting
- Prettier for code formatting

## Project Structure

```
fullstack-app/
├── client/                 # React frontend
│   ├── public/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       ├── utils/
│       └── App.js
├── server/                 # Node.js/Express backend
│   ├── config/
│   ├── controllers/
│   ├── middleware/
│   ├── models/
│   ├── routes/
│   ├── seeders/
│   └── server.js
├── .env                    # Environment variables
├── package.json            # Dependencies and scripts
└── README.md               # This file
```

## Setup Instructions

### Prerequisites
- Node.js (v16 or higher)
- npm or yarn

### Installation Steps

1. Clone the repository:
```bash
git clone <repository-url>
cd fullstack-app
```

2. Install backend dependencies:
```bash
cd server
npm install
```

3. Install frontend dependencies:
```bash
cd ../client
npm install
```

4. Create environment variables file:
```bash
cp .env.example .env
```

5. Run database migrations:
```bash
cd ../server
npx sequelize db:migrate
```

6. Start the development servers:
```bash
# In server directory
npm run dev

# In client directory
npm start
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/profile` - Get current user profile

### Users
- `GET /api/users` - Get all users
- `GET /api/users/:id` - Get user by ID
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Delete user

### Resources (example)
- `GET /api/resources` - Get all resources
- `GET /api/resources/:id` - Get resource by ID
- `POST /api/resources` - Create new resource
- `PUT /api/resources/:id` - Update resource
- `DELETE /api/resources/:id` - Delete resource

## Development Scripts

### Backend
- `npm run dev` - Start development server
- `npm run test` - Run tests
- `npm run lint` - Run linter

### Frontend
- `npm start` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run linter

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a pull request

## License

This project is licensed under the MIT License.