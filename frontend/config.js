const config = {
    development: {
        apiUrl: 'http://localhost:5000'
    },
    production: {
        apiUrl: 'https://ai-assistant-backend-7yp9.onrender.com'  // Your actual Render.com URL
    }
};

// Use the appropriate configuration based on the environment
const environment = process.env.NODE_ENV || 'development';
export const apiUrl = config[environment].apiUrl; 