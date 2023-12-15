from datetime import datetime
from email_validator import EmailNotValidError, validate_email
from flask import request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from flask_restful import Resource
from config import Config
from mysql_connection import get_connection
from mysql.connector import Error
import boto3

from utils import check_password, hash_password


class PhotoPostResource(Resource):
    # 컨텐츠 업로드
    @jwt_required()
    def post(self):

        file = request.files.get('photo')
        content = request.form.get('content')

        user_id = get_jwt_identity()

        if file is None :
            return {"error":"파일을 업로드 하세요."}, 400
        
        current_time = datetime.now()
        new_file_name = current_time.isoformat().replace(':', '_') +'jpeg'

        file.filename = new_file_name

        s3 = boto3.client('s3',
                          aws_access_key_id = Config.AWS_ACCESS_KEY,
                          aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)
        
        try:
            s3.upload_fileobj(file, Config.S3_BUCKET,
                              file.filename,
                              ExtraArgs = {'ACL':'public-read',
                                           'ContentType':'image/jpeg'})
        
        except Exception as e:
            print(e)
            return {'error':str(e)}, 500

        try:
            connection = get_connection()
            query = '''insert into photo
                        (imgUrl, userId, content)
                        values
                        (%s, %s, %s);'''
            
            imgUrl = Config.S3_LOCATION + file.filename

            record = (imgUrl, user_id, content)

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

        return {"result":"success",
                "imgUrl":imgUrl,
                "content":content}, 200
    


