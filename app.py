from flask import Flask, render_template, request, flash
from flask_mysqldb import MySQL
from datetime import datetime
from cache import Cache
from datetime import datetime, timedelta
import boto3
import os


app = Flask(__name__)


app.config['MYSQL_HOST'] = 'memcache-database.cz0uhkdlsnct.us-east-1.rds.amazonaws.com'
app.config['MYSQL_USER'] = 'admin'
app.config['MYSQL_PASSWORD'] = '12345678'
app.config['MYSQL_DB'] = 'Memcache_Database'
app.secret_key = "my-secret-key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


mysql = MySQL(app)
s3 = boto3.resource("s3")
autoscaling = boto3.client('autoscaling')
cache = Cache(500, "random-replacement")


@app.route("/", methods=['POST', 'GET'])
@app.route("/memory_configuration/", methods=['POST', 'GET'])
def memory_configuration():
    if request.method == 'POST':
        flash_message = 'Memcache Configurations are set successfully!'
        capacity = request.form['capacity']
        replacement_policy = request.form['replacement-policy']
        memcache_pool_resizing_option = request.form['memcache-pool-resizing-option']
        if memcache_pool_resizing_option == 'manual':
            autoscaling.put_scaling_policy(AutoScalingGroupName = 'memcache-asg', PolicyName = 'Expand-Automatic-Scaling-Policy', Enabled = False, AdjustmentType = 'PercentChangeInCapacity', ScalingAdjustment = 100)
            autoscaling.put_scaling_policy(AutoScalingGroupName = 'memcache-asg', PolicyName = 'Shrink-Automatic-Scaling-Policy', Enabled = False, AdjustmentType = 'PercentChangeInCapacity', ScalingAdjustment = -50)
            pool_size_option = request.form['pool-size-option']
            pool_resize_number = int(request.form['pool-resize-number'])
            asg_dict = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=['memcache-asg'])
            asg_capacity = asg_dict["AutoScalingGroups"][0]['DesiredCapacity']
            if pool_size_option == 'expand':
                if asg_capacity + pool_resize_number <= 8:
                    autoscaling.set_desired_capacity(AutoScalingGroupName = 'memcache-asg', DesiredCapacity = asg_capacity + pool_resize_number)
                else:
                    flash_message = 'Failed! Expanded Capacity is greater than 8'
            else:
                if asg_capacity - pool_resize_number >= 1:
                    autoscaling.set_desired_capacity(AutoScalingGroupName = 'memcache-asg', DesiredCapacity = asg_capacity - pool_resize_number)
                else:
                    flash_message = 'Failed! Shrinked Capacity is less than 1'
        else:
            autoscaling.put_scaling_policy(AutoScalingGroupName = 'memcache-asg', PolicyName = 'Expand-Automatic-Scaling-Policy', Enabled = True, PolicyType = 'SimpleScaling', AdjustmentType = 'PercentChangeInCapacity', ScalingAdjustment = 100)
            autoscaling.put_scaling_policy(AutoScalingGroupName = 'memcache-asg', PolicyName = 'Shrink-Automatic-Scaling-Policy', Enabled = True, PolicyType = 'SimpleScaling', AdjustmentType = 'PercentChangeInCapacity', ScalingAdjustment = -50)
        clear_cache = request.form['clear-cache']
        delete_application_data = request.form['delete-application-data']
        cursor = mysql.connection.cursor()
        if delete_application_data == 'yes':
            cursor.execute("DELETE FROM image")
            bucket = s3.Bucket('memcache-cloud-bucket')
            bucket.objects.all().delete()
            # list = os.listdir('static/destination_images/')
            # for file in list:
            #     if os.path.exists('static/destination_images/'):
            #         os.remove('static/destination_images/' + file)
        if clear_cache == 'yes':
            cache.clear()
        cursor.execute("UPDATE memory_configuration SET capacity = %s, replacement_policy = %s, clear_cache = %s WHERE seq = 1", (capacity, replacement_policy, clear_cache))
        mysql.connection.commit()
        cursor.close()
        cache.refreshConfiguration(int(capacity), replacement_policy)
        flash(flash_message)
    return render_template("memory_configuration.html")


@app.route("/memory_statistics/")
def memory_statistics():
    beforeTenMins = str(datetime.now() - timedelta(minutes=10))
    beforeTenMins = beforeTenMins[:beforeTenMins.index('.')]
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM memory_statistics WHERE date_created > \'{a:s}\'"
    query = query.format(a = beforeTenMins)
    cursor.execute(query)
    statistics = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    return render_template("memory_statistics.html", data = [item for item in range(1, 31)])


app.run(host='0.0.0.0', port=80, debug=True)
