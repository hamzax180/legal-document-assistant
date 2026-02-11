from backend.app import app

# Vercel looks for 'app', 'application', 'handler', 'server'
# Expose app directly
handler = app
