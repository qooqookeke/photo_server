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

            # 1. posting 테이블에 저장
            query = '''insert into posting
                        (userId, imgUrl, content)
                        values
                        (%s, %s, %s);'''
            
            imgUrl = Config.S3_LOCATION + file.filename

            record = (user_id, imgUrl, content)

            cursor = connection.cursor()
            cursor.execute(query, record)

            posting_id = cursor.lastrowid


            # 2. tag_name 테이블에 저장
            # 리코그니션을 이용해서 받아온 label(tag)이
            # tag_name 테이블에 이미 존재하면 그 아이디만 가져오고
            # 그렇지 않으면 테이블에 인서트 한후에 그 아이디를 가져온다.
            for tag in tag_list: # 반복문
                tag = tag.lower() # 태그 소문자로 통일 저장
                query = '''select *
                            from tag_name
                            where name = %s;'''
                record = (tag.lower(), )

                cursor = connection.cursor(dictionary=True)
                cursor.execute(query, record)

                result_list = cursor.fetchall()

                # 태그가 이미 테이블에 있으면 아이디만 가져오고
                if len(result_list) != 0:
                    tag_name_id = result_list[0]['id']

                # 태그가 테이블에 없으면 인서트 한다.
                else:
                    query = '''insert into tag_name
                                (name)
                                values
                                (%s);'''
            
                    record = (tag, )

                    cursor = connection.cursor()
                    cursor.execute(query, record)

                    tag_name_id = cursor.lastrowid

            # 3. tag 테이블에 저장
            # 위의 태그 네임 아이디와 포스팅아이디를 이용해서
            # tag테이블에 데이터를 넣어준다.
                query = '''insert into tag
                            (postingId, tagNameId)
                            values
                            (%s, %s);'''
  
                record = (posting_id, tag_name_id)

                cursor = connection.cursor()
                cursor.execute(query, record)

            # 트랜잭션 처리를 위해서 커밋은 테이블 처리를 다 하고나서
            # 마지막에 한번 해준다.
            # 이렇게 하면 중간에 다른 테이블에서 문제가 발생하면
            # 모든 테이블이 원상복구(롤백)된다.
            # 이 기능을 트랜잭션이라고 한다.
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


    # 친구 컨텐츠 보기
    @jwt_required()
    def get(self):

        offset = request.args.get('offset')
        limit = request.args.get('limit')
        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            query = '''select p.id as photoId, p.imgUrl, p.content, 
                                u.id as userId, u.email, 
                                p.createdAt, count(l.id) as likeCnt, 
                                if(l2.id is null, 0, 1) as isLike
                        from follow f
                        join posting p
                        on f.followeeId = p.userId
                        join user u
                        on p.userId = u.id
                        left join `like` l
                        on p.id = l.postingId
                        left join `like` l2
                        on p.id = l2.postingId and l2.userId = %s
                        where followerId = %s
                        group by p.id
                        order by p.createdAt desc
                        limit '''+offset+''', '''+limit+''';'''
            record = (user_id, user_id)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            i = 0
            for row in result_list:
                result_list[i]['createdAt'] = row['createdAt'].isoformat()
                i = i + 1

            cursor.close()
            connection.close()
        
        except Error as e:
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500

        return {"result":"success", 
                "items":result_list,
                "count":len(result_list)}, 200
    

class PostingResource(Resource):
    # 포스팅 상세정보
    @jwt_required()
    def get(self, posting_id):

        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            
            # 포스팅 상세정보 쿼리
            query = '''select p.id as postId, p.imgurl, p.content, 
                                u.id as userId, u.email, p.createdAt, 
                                count(l.id) as likeCnt, 
                                if(l2.id is null, 0, 1) as isLike
                        from posting p
                        join user u
                        on p.userId = u.id
                        left join `like` l
                        on p.id = l.postingId
                        left join `like` l2
                        on p.id = l2.postingId and l2.userId = %s
                        where p.id = %s;'''
            record = (user_id, posting_id)
        
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            if len(result_list) == 0 :
                return {"error":"데이터가 없습니다."}, 400 
            
                                    
            print(result_list)

            # 데이터 변수 작업
            post = result_list[0]


            # 포스팅 상세정보 태그 정보 쿼리
            query = '''select concat('#', tn.name) as tag
                        from tag t
                        join tag_name tn
                        on t.tagNameId = tn.id
                        where postingId = %s;'''
            
            record = (posting_id, )

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            print(result_list)

            tag = [] # 빈 리스트 만들기
            for tag_dict in result_list:
                tag.append(tag_dict['tag'])

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500
        
        
        post['createdAt'] = post['createdAt'].isoformat()
        
        
        return {"result":"success",
                "post":post,
                "tag":tag}, 200
    

 