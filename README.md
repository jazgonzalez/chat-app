# Real-Time Chat Application
This Real-time messaging platform  project demonstrates advanced integration of NoSQL databases, secure user authentication, and WebSocket communication.

## Features

* **Real-Time Communication**: Instant message delivery and room announcements implemented with Flask-SocketIO.
* **Secure Authentication**: User registration and login system using bcrypt for password hashing.
* **Multimedia Storage**: Support for uploading and streaming image and audio files via MongoDB GridFS.
* **Room Management**: Functionality to create private rooms, add or remove members, and manage administrative rights.
* **Message History**: Efficient retrieval of older messages using AJAX and MongoDB pagination.

## Tech Stack

* **Backend**: Python 3.13+ with Flask.
* **Database**: MongoDB Atlas using PyMongo.
* **File System**: MongoDB GridFS for binary data.
* **Real-Time**: Flask-SocketIO.


## Project Structure

* **app.py**: Main application logic and SocketIO event handling.
* **db.py**: Database connection string and CRUD operations for rooms and messages.
* **user.py**: User class definition and password validation methods.
* **templates/**: Jinja2 HTML templates for the frontend.
* **static/**: Directory for CSS and JavaScript assets.
* **requirements.txt**: List of all Python dependencies.

## Installation and Setup

1. **Clone the repository**:
   `git clone https://github.com/jazgonzalez/chat-app.git`

2. **Set up a virtual environment**:
   `python -m venv .venv`.
   `source .venv/bin/activate` (Use `.venv\Scripts\activate` on Windows).

3. **Install dependencies**:
   `pip install -r requirements.txt`.

4. **Environment Variables**:
   Create a `.env` file to store your `MONGO_URI` and `SECRET_KEY`. This file is ignored by Git for security.

5. **Run the application**:
   `python app.py`.


