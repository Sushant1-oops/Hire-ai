# Frontend Setup Guide

This is a professional HR Assistant frontend built with React, Vite, and Tailwind CSS.

## Features

- ✨ **Modern UI** - Clean, professional interface with Tailwind CSS
- 🔐 **Authentication** - Secure login/registration with JWT tokens
- 📤 **Resume Upload** - Drag-and-drop resume upload with file validation
- 🔍 **Candidate Search** - AI-powered semantic search for candidates
- 📊 **Analytics Dashboard** - Monitor hiring metrics and statistics
- 💼 **Responsive Design** - Works seamlessly on desktop and tablet
- ⚡ **Fast Performance** - Built with Vite for optimal speed

## Installation

### Prerequisites
- Node.js 16+ 
- npm or yarn

### Setup Steps

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Start development server:**
```bash
npm run dev
```

The frontend will run at `http://localhost:5173`

## Environment Configuration

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api
```

## Project Structure

```
frontend/
├── src/
│   ├── components/         # Reusable React components
│   │   ├── Header.jsx      # Top navigation bar
│   │   ├── Sidebar.jsx     # Left navigation sidebar
│   │   ├── Analytics.jsx   # Dashboard analytics
│   │   ├── ResumeUpload.jsx # Resume upload component
│   │   └── CandidateSearch.jsx # Candidate search component
│   ├── pages/              # Page components
│   │   ├── Login.jsx       # Login/Register page
│   │   └── Dashboard.jsx   # Main dashboard page
│   ├── utils/              # Utility functions
│   │   └── api.js          # API request wrapper
│   ├── App.jsx             # Root component
│   ├── main.jsx            # Entry point
│   ├── index.css           # Global styles with Tailwind
│   └── App.css             # App-specific styles
├── package.json
└── vite.config.js
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Tech Stack

- **React 19** - UI library
- **Vite 7** - Build tool and dev server
- **Tailwind CSS 4** - Styling
- **React Feather** - Icon library
- **Fetch API** - HTTP requests

## Features Overview

### Authentication
- User registration with email validation
- Secure JWT token storage
- Automatic logout on token expiration
- Demo credentials for testing

### Dashboard
- Real-time statistics
- Recent activity feed
- Quick access to main features

### Resume Management
- Drag-and-drop file upload
- PDF and DOCX support
- File validation
- Upload progress tracking
- Success/error feedback

### Candidate Search
- AI-powered semantic search
- Advanced filtering options
- Match scoring
- Quick actions (view profile, send interview)

## API Integration

The frontend connects to the FastAPI backend. Ensure the backend is running on `http://localhost:8000`.

### Required API Endpoints

- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/resume/upload` - Resume upload
- `GET /api/candidates` - Fetch candidates
- `POST /api/candidates/search` - Search candidates

## Database Note

The backend uses PostgreSQL for data persistence. Ensure PostgreSQL is properly configured in your `.env` file:

```
DATABASE_URL=postgresql://user:password@localhost:5432/hr_assistant
```

## Performance Optimizations

- Lazy loading of components
- Image optimization with Tailwind
- CSS-in-JS with Tailwind JIT
- Minified production builds
- Browser caching with Vite

## Customization

### Changing Colors
Edit Tailwind config in `vite.config.js` to customize the color scheme.

### Adding Components
Follow the existing component structure in `src/components/`.

### API Configuration
Update the API_BASE_URL in `src/utils/api.js` if backend is hosted elsewhere.

## Troubleshooting

### Connection Error
- Ensure the backend is running on `http://localhost:8000`
- Check CORS settings in the backend

### Build Issues
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

### Styling Issues
- Ensure Tailwind CSS is properly installed
- Check `tailwindcss` version in package.json

## Development Tips

1. **Hot Module Replacement** - Changes are reflected instantly
2. **React DevTools** - Install browser extension for debugging
3. **Network Inspector** - Use browser DevTools to debug API calls
4. **Console Logs** - Check browser console for errors

## Production Build

```bash
npm run build
```

This creates an optimized build in the `dist/` folder.

## Contributing

Follow the existing code style and component structure when adding new features.

## Support

For issues or questions, refer to the backend documentation or check the API logs.
