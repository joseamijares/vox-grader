"""Environment loader for Railway deployment.
Falls back to file-based .env for local development."""
import os

def load_env():
    """Load environment variables. On Railway they're already set.
    Locally, load from .env file."""
    # Railway sets these automatically
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        return
    
    # Local development - load from file
    env_path = os.path.expanduser('~/dev/vox-python/.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k not in os.environ:
                        os.environ[k] = v.strip('"').strip("'")
