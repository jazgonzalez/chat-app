from werkzeug.security import check_password_hash

class User:
    #constructor
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = password

    #Methods
    @staticmethod
    def is_authenticated():
        return True
    
    @staticmethod
    def is_active():
        return True
    
    @staticmethod
    def is_anonymous():
        return False #there can't be anonymous users
    
    def get_id(self):
        return self.username 
    
    def check_password(self, password_input):
        return check_password_hash(self.password, password_input)