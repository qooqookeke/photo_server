import serverless_wsgi
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_restful import Api
from config import Config
from resources.follow import FollowContentResource, FollowResource
from resources.post import PhotoPostResource
from resources.user import UserLoginResource, UserLogoutResource, UserRegisterResource
from resources.user import jwt_blocklist

app = Flask(__name__)

app.config.from_object(Config)

jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def check_if_token_is_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in jwt_blocklist

api = Api(app)


api.add_resource(UserRegisterResource,'/register')
api.add_resource(UserLoginResource,'/login')
api.add_resource(UserLogoutResource,'/logout')
api.add_resource(PhotoPostResource,'/upload')
api.add_resource(FollowResource,'/follow/<int:followee_id>')
api.add_resource(FollowContentResource,'/follow/content')



if __name__ == '__main__':
    app.run()
