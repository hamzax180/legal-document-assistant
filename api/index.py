from backend.app import app

# Vercel looks for 'app', 'application', 'handler', 'server'
# Expose app directly
# handler = app  <-- Removed alias to avoid Vercel treating it as class-based handler
