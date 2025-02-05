from authApp import app, init_db
import allRoutes  # Ensure routes are registered
from notifications import notificationApp  # Import the notifications module

if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(host='0.0.0.0', port=5000, debug=True)

