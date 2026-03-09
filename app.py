from datetime import datetime, timezone
from bson.json_util import dumps
import base64, mimetypes
from flask import jsonify     

from flask import Flask, render_template, request, redirect, url_for, Response
from flask_login import LoginManager, login_user, login_required, \
                        logout_user, current_user
from flask_socketio import SocketIO, join_room, leave_room
from pymongo.errors import DuplicateKeyError

from db import (add_room_members, get_file, get_messages, get_room,
                get_room_members, get_rooms_for_user, get_user, is_room_admin,
                is_room_member, remove_room_members, save_file, save_message,
                save_room, save_user, update_room)

def split_and_clean(raw: str) -> list[str]:
    """
    Convierte 'u1 , u2,' → ['u1', 'u2'].
    Elimina espacios y entradas vacías.
    """
    if not raw:
        return []
    return [u.strip() for u in raw.split(',') if u.strip()]

app= Flask (__name__)
app.secret_key = "me secret key"    #google how to define the secret key
socketio=SocketIO(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ─── ROUTE that serves images / audio stored in GridFS ──────────
@app.route("/file/<file_id>")
def serve_file(file_id):
    """
    Streams a file stored in GridFS (/uploads) back to the browser.
    The <file_id> is the _id we saved in save_file().
    """
    gfile = get_file(file_id)                # GridOut object
    return Response(
        gfile.read(),
        content_type=gfile.content_type,
        headers={
            "Content-Disposition":
            f'inline; filename="{gfile.filename or file_id}"'
        }
    )

@app.context_processor
def inject_helpers():
    return dict(is_room_admin=is_room_admin)


#HOME PAGE
@app.route('/')
def home():
    rooms = []
    if current_user.is_authenticated: #is the current user is authenticated
        rooms = get_rooms_for_user(current_user.username) #return a list of rooms
    return render_template("index.html", rooms=rooms) 


#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    #if current_user.is_authenticated:
        #return redirect(url_for('home'))

    message = ''
    if request.method == 'POST':
        username = request.form.get('username') #get username from the form
        password_input = request.form.get('password') #get password from the form
        user = get_user(username)

        #if user exists and password is correct
        if user and user.check_password(password_input):
            login_user(user)    #logs the user
            return redirect(url_for('home'))
        else:   #if it doesnt exists or password is incorrect
            message = 'Failed to login!'    #prints a message
    return render_template('login.html', message=message)   #and still remains in the login page

#SIGN UP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    #if current_user.is_authenticated:
        #return redirect(url_for('home'))    #if the user is authenticated it redirects to home page

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            save_user(username, email, password)
            return redirect(url_for('login'))
        except DuplicateKeyError: #if the username already exists
            message = "User already exists!"
    return render_template('signup.html', message=message)


#LOG OUT
@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))  #redirect to home page when user is logged out


#CREATE ROOM
@app.route('/create-room/', methods=['GET', 'POST'])
@login_required
def create_room():
    message = ''
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        raw       = request.form.get('members', '')          # ← texto crudo del form
        usernames = split_and_clean(raw)                     ### limpia y separa

        # el creador siempre será miembro-admin
        room_id = save_room(room_name, current_user.username)

        # quita duplicados y tu propio nombre
        usernames = {u for u in usernames if u and u != current_user.username}

        # ───── verificar existencia en la tabla users ─────
        invalid = [u for u in usernames if not get_user(u)]
        if invalid:
            message = f"The following users don't exist: {', '.join(invalid)}"
            # vuelve a mostrar el form con el texto original
            return render_template('create_room.html',
                                   message=message,
                                   room_name=room_name,
                                   members=raw)

        # todo OK → agrega miembros válidos
        if usernames:
            add_room_members(room_id, room_name, list(usernames), current_user.username)

        return redirect(url_for('view_room', room_id=room_id))

    # GET
    return render_template('create_room.html', message=message)


#EDIT ROOMS
@app.route('/rooms/<room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = get_room(room_id)
    if not room or not is_room_admin(room_id, current_user.username):
        return "Room not found", 404

    existing = [m['_id']['username'] for m in get_room_members(room_id)
                if m['_id']['username']]
    room_members_str = ",".join(existing)
    message = ''

    if request.method == 'POST':
        room_name   = request.form.get('room_name')
        raw_members = request.form.get('members', '')
        new_members = [u.strip() for u in raw_members.split(',') if u.strip()]

        # el admin no puede salir
        if current_user.username not in new_members:
            new_members.append(current_user.username)

        # validar usuarios
        invalid = [u for u in new_members if not get_user(u)]
        if invalid:
            message = f"Users don't exist..can't add them: {', '.join(invalid)}"
            return render_template('edit_room.html',
                                   room=room,
                                   room_members_str=",".join(new_members),
                                   message=message)

        to_add    = list(set(new_members) - set(existing))
        to_remove = list(set(existing)    - set(new_members))
        if to_add:
            add_room_members(room_id, room_name, to_add, current_user.username)
        if to_remove:
            remove_room_members(room_id, to_remove)

        update_room(room_id, room_name)
        return redirect(url_for('view_room', room_id=room_id))
    # GET normal: simplemente mostrar el formulario
    return render_template('edit_room.html',
                           room=room,
                           room_members_str=room_members_str,
                           message=message)


#──────────VIEW ROOM──────────
@app.route('/rooms/<room_id>/')
@login_required #user must be logged in
def view_room(room_id):
    room = get_room(room_id)
    #if the user is a member of the room
    if room and is_room_member(room_id, current_user.username):
        room_members = get_room_members(room_id) #room members list
        messages = get_messages(room_id) #view the messages
        return render_template('view_room.html', username=current_user.username, room=room, room_members=room_members, messages=messages)
    else:
        return "Room not found", 404


#──────────TO VIEW OLDER MESSAGES──────────
@app.route("/rooms/<room_id>/messages/") 
@login_required
def get_older_messages(room_id):
    """AJAX: return one 'page' of older messages for infinite-scroll."""
    if not (room := get_room(room_id)):
        return "Room not found", 404
    if not is_room_member(room_id, current_user.username):
        return "Room not found", 404

    page      = int(request.args.get("page", 0))
    messages  = get_messages(room_id, page)  # list[dict]

    # bson.json_util.dumps() turns ObjectId → {"$oid": "..."} automatically
    return Response(
        dumps(messages), # JSON string
        mimetype="application/json"  
    )
    
#──────────SEND MESSAGES──────────
@socketio.on('send_message')
def handle_send_message_event(data):
    #announce that someone sent a message to the room
    app.logger.info("{} has sent message to the room {}: {}".format(data['username'],
                                                                    data['room'],
                                                                    data['message']))
    #shows the time of the message
    data['created_at'] = datetime.now().strftime("%d %b, %H:%M")
    save_message(data['room'], data['message'], data['username']) #room,message,sender
    #check what sockets are port of the room and send the event only to those sockets
    socketio.emit('receive_message', data, room=data['room'])



#──────────client sends a FILE (image / audio)──────────
@socketio.on('send_file')                   
def handle_send_file(data):
    # --- 1.  Strip the data: URL header and decode Base-64 -----------
    b64   = data['b64'].split(',')[-1]          # keep only pure base64
    blob  = base64.b64decode(b64)               # bytes of the file

    # --- 2.  Detect MIME type from the filename ----------------------
    mime, _ = mimetypes.guess_type(data['filename'])

    # --- 3.  Store the file in GridFS and keep its _id --------------
    file_id = save_file(blob, mime or "application/octet-stream")

    # --- 4.  Decide whether it’s image or audio ----------------------
    kind = "image" if mime and mime.startswith("image/") else "audio"

    # --- 5.  Persist a message in the 'messages' collection ---------
    save_message(
        data['room'],                 # room_id
        '',                           # no text content
        data['username'],             # sender
        msg_type=kind,                # "image" or "audio"
        file_id=file_id,              # GridFS reference
        mime=mime                     # MIME type
    )

    # --- 6.  Broadcast to every socket in the same room -------------
    socketio.emit(
        'receive_message',            # clients already listen to this
        {
            "username":  data['username'],
            "room":      data['room'],
            "message":   '',                          # empty text
            "created_at": datetime.now()
                           .strftime("%d %b, %H:%M"), # nice timestamp
            "type":      kind,                        # for the client
            "file_id":   file_id,                     # /file/<id> route
            "mime":      mime
        },
        room=data['room']             # target only that chat room
    )


#──────────JOIN ROOM ANNOUNCEMENT──────────
@socketio.on('join_room')
def handle_join_room_event(data):
    room = data['room']
    username = data['username']
    #join the room socket
    join_room(room)
    app.logger.info(f"{username} has joined room {room}")
    #emit message to other members 
    socketio.emit(
        'join_room_announcement',
        {
            'username': username,
           'Timestamp': datetime.now().strftime("%H:%M")
        },
        room=room,
    )

#──────────LEAVE ROOM ANNOUNCEMENT──────────
@socketio.on('leave_room')
def handle_leave_room_event(data):
    room = data['room']
    username = data['username']
    #remove socket from the room
    leave_room(room)
    app.logger.info(f"{username} has left room {room}")
    #emits message to everyone in the room 
    socketio.emit(
        'leave_room_announcement',
        {
            'username': username,
            'timestamp': datetime.now().strftime("%H:%M")
        },
        room=room  # joiner sees it too
    )

@login_manager.user_loader
def load_user(username): 
    return get_user(username)


if __name__ == '__main__':
    socketio.run(app,debug=True)