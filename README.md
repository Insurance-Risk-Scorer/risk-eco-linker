# Environmental Risk Scorer

# EXPLAINING VIDEO WALKTHROUGH: https://www.loom.com/share/3058f9451642467c8170d73be81ef338

A professional property risk assessment platform for insurance underwriters. Get comprehensive flood, wildfire, storm, and drought risk analysis powered by AI and Google Earth Engine.

## Features

- **AI-Powered Risk Assessment**: Comprehensive analysis of environmental risks using Google Gemini AI
- **Multi-Hazard Analysis**: Evaluate flood, wildfire, storm, and drought risks
- **Google Earth Engine Integration**: Advanced wildfire risk calculations using satellite data
- **Interactive Maps**: Visualize property locations and risk factors
- **Automated Decision Support**: AI-generated recommendations for insurance underwriting
- **Modern UI**: Built with React, TypeScript, and shadcn/ui components

## Tech Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **React Router** for navigation
- **TanStack Query** for data fetching
- **Tailwind CSS** for styling
- **shadcn/ui** for UI components
- **Recharts** for data visualization

### Backend
- **Flask** (Python) REST API
- **Google Gemini AI** for risk analysis
- **Google Earth Engine** for wildfire risk calculations
- **Geopy** for geocoding

## Prerequisites

- **Node.js** 20.x or higher
- **Python** 3.13 or higher
- **npm** or **bun** package manager
- **Google Gemini API Key** (for AI risk analysis)
- **Mapbox API Key** (optional, for enhanced map features)

## Setup Instructions

### Frontend Setup

1. Install dependencies:
```bash
npm install
# or
bun install
```

2. Create a `.env` file in the root directory (optional):
```env
VITE_MAPBOX_API_KEY=your_mapbox_api_key_here
```

3. Start the development server:
```bash
npm run dev
# or
bun dev
```

The frontend will be available at `http://localhost:8080`

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

4. Install Python dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file in the `backend` directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

6. Start the Flask server:
```bash
python app.py
```

The backend API will be available at `http://localhost:5001`

## Building for Production

### Frontend

Build the production bundle:
```bash
npm run build
# or
bun run build
```

The built files will be in the `dist/` directory.

Preview the production build:
```bash
npm run preview
# or
bun run preview
```

### Backend

The backend is ready for deployment. For production, use a WSGI server like Gunicorn:
```bash
gunicorn app:app --bind 0.0.0.0:5001
```

## Project Structure

```
environmental-risk-scorer/
├── backend/              # Flask API server
│   ├── app.py           # Main Flask application
│   ├── wildfire_risk_ee.py  # Earth Engine integration
│   └── requirements.txt # Python dependencies
├── src/                 # React frontend source
│   ├── components/      # React components
│   ├── pages/           # Page components
│   ├── hooks/           # Custom React hooks
│   └── lib/             # Utility functions
├── public/              # Static assets
├── dist/                # Production build output (generated)
└── vite.config.ts       # Vite configuration
```

## API Endpoints

### POST `/api/get-risk-report`

Generate a comprehensive risk assessment for a property.

**Request Body:**
```json
{
  "address": "123 Main St, City, State, ZIP",
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

**Response:**
```json
{
  "overall_summary": "...",
  "automated_decision": "APPROVE|REJECT|REVIEW",
  "flood_risk": {...},
  "wildfire_risk": {...},
  "storm_risk": {...},
  "drought_risk": {...}
}
```

## Environment Variables

### Frontend
- `VITE_MAPBOX_API_KEY` (optional): Mapbox API key for enhanced map features

### Backend
- `GEMINI_API_KEY` (required): Google Gemini API key for AI risk analysis

## Development

### Running Linter

```bash
npm run lint
```

### Development Mode

The frontend development server includes a proxy configuration that forwards `/api` requests to the backend. In production, the frontend makes direct API calls to the configured backend URL.

## Deployment

### Frontend Deployment

The frontend can be deployed to any static hosting service:
- **Vercel**: Connect your repository and deploy
- **Netlify**: Connect your repository and set build command to `npm run build`
- **GitHub Pages**: Use GitHub Actions to build and deploy
- **Cloudflare Pages**: Connect repository and set build command

### Backend Deployment

The backend can be deployed to:
- **Render**: Connect repository and set start command to `gunicorn app:app`
- **Heroku**: Use the Procfile with `web: gunicorn app:app`
- **AWS Elastic Beanstalk**: Configure for Python/Flask
- **Google Cloud Run**: Containerize and deploy

**Note**: Ensure environment variables are set in your deployment platform.

## License

See [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues and questions, please open an issue on the GitHub repository.
