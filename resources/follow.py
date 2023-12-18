from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql_connection import get_connection
from mysql.connector import Error


class FollowResource(Resource):
    # 친구 맺기
    @jwt_required()
    def post(self, followee_id):

        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            query = '''insert into follow
                        (followerId, followeeId)
                        values
                        (%s, %s);'''
            record = (user_id, followee_id)

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
    

    # 친구 끊기
    @jwt_required()
    def delete(self, followee_id):

        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            query = '''delete from follow
                        where followerId = %s and followeeId = %s;'''
            record = (user_id, followee_id)
        
            cursor = connection.cursor()
            cursor.execute(query, record)
            connection.commit()

            cursor.close()
            connection.close()
        except Error as e:
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500
        
        return {"result":"success"}, 200
    

class FollowContentResource(Resource):
    # 친구 컨텐츠 보기
    @jwt_required()
    def get(self):

        offset = request.args.get('offset')
        limit = request.args.get('limit')
        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            query = '''select p.id as photoId, p.userId, 
                        u.email, p.imgUrl, p.content, 
                        p.createdAt, count(l.postId) as likeCnt
                        from follow f
                        join photo p
                        on f.followeeId = p.userId
                        join user u
                        on p.userId = u.id
                        left join islike l
                        on u.id = l.userId 
                        where f.followerId = %s
                        group by p.id
                        order by p.createdAt desc
                        limit '''+offset+''', '''+limit+''';'''
            record = (user_id, )

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            i = 0
            for row in result_list:
                result_list[i]['createdAt'] = row['createdAt'].isoformat()
                result_list[i]['updatedAt'] = row['updatedAt'].isoformat()
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