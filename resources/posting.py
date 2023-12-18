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


class PostingListResource(Resource):
    # 포스팅 생성
    @jwt_required()
    def post(self):

        # 클라이언트가 보낸 내용 받기 
        file = request.files.get('image')
        content = request.form.get('content')

        user_id = get_jwt_identity()

        # 파일 있는지 확인
        if file is None :
            return {"error":"파일을 업로드 하세요."}, 400
        
        # 파일 저장명 지정
        current_time = datetime.now()
        new_file_name = current_time.isoformat().replace(':', '_') + str(user_id) +'jpeg'

        #파일명 수정
        file.filename = new_file_name

        # s3 접근(접속)
        s3 = boto3.client('s3',
                          aws_access_key_id = Config.AWS_ACCESS_KEY,
                          aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)
        
        # s3 파일 업로드(저장)
        try:
            s3.upload_fileobj(file, Config.S3_BUCKET,
                              file.filename,
                              ExtraArgs = {'ACL':'public-read',
                                           'ContentType':'image/jpeg'})
        except Exception as e:
            print(e)
            return {'error':str(e)}, 500
        
        # rekognition 서비스를 이용해서 object detection하여
        # 태그 이름을 가져온다.(오토태깅)
        tag_list = self.detect_labels(new_file_name, Config.S3_BUCKET)

        print(tag_list)

        # DB의 posting 테이블에 데이터를 넣어야하고
        # tag_name 테이블과 tag 테이블에도 데이터를 넣어줘야한다.

        # DB(sql) 연결 후 저장
        try:
            connection = get_connection()

            # posting 테이블에 저장
            query = '''insert into posting
                        (imgUrl, userId, content)
                        values
                        (%s, %s, %s);'''
            
            imgUrl = Config.S3_LOCATION + file.filename

            record = (imgUrl, user_id, content)

            # tag_name 테이블에 저장
            query = '''insert into tag_name
                        (name)
                        values
                        (%s);'''
            
            record = (tag_list, )

            # tag 테이블에 저장
            query = '''insert into tag
                        (postingId, tagId)
                        values
                        (%s, %s);'''
            
            record = (tag_list, )

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
    

    # 오토 태깅(rekognition)
    def detect_labels(self, photo, bucket):

        client = boto3.client('rekognition', 
                              'ap-northeast-2', 
                              aws_access_key_id = Config.AWS_ACCESS_KEY,
                              aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)


        response = client.detect_labels(Image={'S3Object':{'Bucket':bucket,'Name':photo}},
        MaxLabels=5,
        # Uncomment to use image properties and filtration settings
        #Features=["GENERAL_LABELS", "IMAGE_PROPERTIES"],
        #Settings={"GeneralLabels": {"LabelInclusionFilters":["Cat"]},
        # "ImageProperties": {"MaxDominantColors":10}}
        )

        print('Detected labels for ' + photo)
        print()

        labels_list = []
        for label in response['Labels']:
            print("Label: " + label['Name'])
            print("Confidence: " + str(label['Confidence']))
                        
            # confidence(정확도)가 90이상인 label 이름만 
            # 클라이언트에게 응답하도록 코드수정하세요
            if label['Confidence'] >= 90 :
                labels_list.append(label['Name'])
        

        return labels_list
