from flask import Flask, render_template
import os

app = Flask(__name__, 
            template_folder='/Users/engineers/EDDA/admin_platform/app/templates',
            static_folder='/Users/engineers/EDDA/admin_platform/app/static')

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
