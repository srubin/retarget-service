from datetime import timedelta

## Broker settings.
BROKER_URL = 'amqp://guest:guest@localhost:5672//'

CELERY_IMPORTS = ('retarget_service')

CELERY_RESULT_BACKEND = 'amqp'
CELERY_TASK_RESULT_EXPIRES = 18000

CELERYBEAT_SCHEDULE = {
    'clean-generated-every-hour': {
        'task': 'retarget-service.clean_generated',
        'schedule': timedelta(hours=1)
    },
    'clean-uploads-every-hour': {
        'task': 'retarget-service.clean_uploads',
        'schedule': timedelta(hours=1)
    }
}
