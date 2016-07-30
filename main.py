from webapp.webapp import app
import sys

if __name__ == '__main__':
    context = ('santihub.crt', 'santihub.key')
    try:
        app.run(host='0.0.0.0', ssl_context=context, threaded=True)
    except KeyboardInterrupt:
        print("Bye")
        sys.exit()

