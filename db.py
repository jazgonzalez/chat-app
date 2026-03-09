from datetime import datetime
from bson import ObjectId
from pymongo import DESCENDING, MongoClient
from werkzeug.security import generate_password_hash
from gridfs import GridFS  # Import GridFS to store large binary files in MongoDB
from user import User

# ─── CONNECTION ──────────────────────────────────────────────────────────
client = MongoClient("mongodb+srv://chatapp:chatapp@chatapp.pom8hbn.mongodb.net/?retryWrites=true&w=majority&appName=ChatApp")
chat_db = client.get_database("ChatDB") 

# ───Collections in the database ───────────────────────────────────
users_collection = chat_db.get_collection("users") #users info (id,email,password)
rooms_collection = chat_db.get_collection("rooms") #rooms info (id, name, created by, created at)
room_members_collection = chat_db.get_collection("room_members") #members of the room (id, room name, added by, added at, is room admin)
messages_collection = chat_db.get_collection("messages") #messages of each room (id, room id, text, sender, created at)
fs = GridFS(chat_db, collection="uploads")  # Create a GridFS bucket named “uploads” inside the chat_db database

# ─── helper functions for GridFS ───────────────────────────────────
def save_file(binary_data: bytes, mime: str) -> str:
    """Store the file in GridFS and return its _id as string"""
    return str(fs.put(binary_data, content_type=mime))

def get_file(file_id: str):
    """Retrieve the GridFS file (GridOut) by its _id"""
    return fs.get(ObjectId(file_id))


#─── function to save data from user  ───────────────────────────────────
def save_user(username, email, password):
    #generates password hash from the password
    password_hash = generate_password_hash(password)
    #insert data into the collection where username is the primary key (unique)
    users_collection.insert_one({'_id': username, 'email': email, 'password': password_hash})

#function to get the user from the database
def get_user(username):
    user_data = users_collection.find_one({'_id': username}) #get all the information from the user
    return User(user_data['_id'], user_data['email'], user_data['password']) if user_data else None

#FUNCTION TO SAVE A ROOM
def save_room(room_name, created_by):
    room_id = rooms_collection.insert_one(
        {'name': room_name, 'created_by': created_by, 'created_at': datetime.now()}).inserted_id
    add_room_member(room_id, room_name, created_by, created_by, is_room_admin=True) #first person to be added is the admin
    return room_id

#FUNCTION TO UPDATE THE NAME OF THE ROOM
def update_room(room_id, room_name):
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {'name': room_name}}) #set the new room name in rooms collection
    room_members_collection.update_many({'_id.room_id': ObjectId(room_id)}, {'$set': {'room_name': room_name}}) #set the new room name in room_members collection

#FUNCTION TO VIEW THE ROOM
def get_room(room_id):
    return rooms_collection.find_one({'_id': ObjectId(room_id)})

#FUNCTION TO ADD MEMEBER THE ADMIN TO THE ROOM
def add_room_member(room_id, room_name, username, added_by, is_room_admin=False):
    room_members_collection.insert_one(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, #unique id key
         'room_name': room_name, 
         'added_by': added_by,'added_at': datetime.now(), 
         'is_room_admin': is_room_admin})

#FUNCTION TO ADD MEMBERS TO THE ROOM
def add_room_members(room_id, room_name, usernames, added_by):
    room_members_collection.insert_many(
        [{'_id': {'room_id': ObjectId(room_id), 'username': username}, 'room_name': room_name, 'added_by': added_by,
          'added_at': datetime.now(), 'is_room_admin': False} for username in usernames])

#FUNCTION TO REMOVE MEMBERS FROM A ROOM
def remove_room_members(room_id, usernames):
    room_members_collection.delete_many(
        {'_id': {'$in': [{'room_id': ObjectId(room_id), 'username': username} for username in usernames]}})

#FUNCTION TO SEE THE ROOM MEMBERS, BY SEARCHING BY ROOM ID
def get_room_members(room_id):
    return list(room_members_collection.find({'_id.room_id': ObjectId(room_id)}))

#FUNTION TO GET THE ROOMS FOR A PARTICULAR USER
def get_rooms_for_user(username):
    return list(room_members_collection.find({'_id.username': username}))

#FUNTION TO SEE IF A USER IS A MEMBER OF A ROOM
def is_room_member(room_id, username):
    return room_members_collection.count_documents({'_id': {'room_id': ObjectId(room_id), 'username': username}})

#FUNCTION TO CHECK IF A USER IS A ROOM ADMIN OR NOT
def is_room_admin(room_id, username):
    return room_members_collection.count_documents(
        {'_id': {'room_id': ObjectId(room_id), 'username': username}, 'is_room_admin': True})

#FUNCTION TO SAVE MESSAGES
# FUNCTION TO SAVE MESSAGES  (text, image or audio)
def save_message(room_id, text, sender,
                 *,                       # keyword-only extras
                 msg_type="text",         # "text", "image", "audio"
                 file_id=None,            # GridFS _id if it’s a file
                 mime=None):              # MIME type for files
    messages_collection.insert_one({
        'room_id':   room_id,
        'text':      text,
        'sender':    sender,
        'type':      msg_type,
        'file_id':   file_id,
        'mime':      mime,
        'created_at': datetime.now()
    })


MESSAGE_FETCH_LIMIT = 3 #skip the first 3 documents 

#get old messages
def get_messages(room_id, page=0):
    offset = page * MESSAGE_FETCH_LIMIT #how many messages we want to skip
    messages= list(messages_collection.find({'room_id': room_id}).sort('_id', DESCENDING).limit(MESSAGE_FETCH_LIMIT).skip(offset))
    for message in messages:
        message['created_at'] = message['created_at'].strftime("%d %b, %H:%M")
    return messages[::-1]
