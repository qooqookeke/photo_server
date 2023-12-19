from datetime import datetime
from email_validator import EmailNotValidError, validate_email
from flask import request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from flask_restful import Resource
from config import Config
from mysql_connection import get_connection
from mysql.connector import Error


class LikeResource(Resource):
     # 좋아요 하기
    @jwt_required()
    def post(self, posting_id):

        user_id = get_jwt_identity()

        try :
            connection = get_connection()
            query = '''insert into `like`
                        (userId, postingId)
                        values
                        (%s, %s);'''
            record = (user_id, posting_id)
        
            cursor = connection.cursor()
            cursor.execute(query, record)
            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500


        return {"result":"success"}, 200
    

    # 좋아요 취소
    @jwt_required()
    def delete(self, posting_id):
        
        user_id = get_jwt_identity()

        try :
            connection = get_connection()
            query = '''delete from `like`
                        where userId = %s and postingId = %s;'''  
            record = (user_id, posting_id)
        
            cursor = connection.cursor()
            cursor.execute(query, record)
            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500


        return {"result":"success"}, 200
    
    