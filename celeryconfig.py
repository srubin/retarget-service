from datetime import timedelta

## Broker settings.
BROKER_URL = 'amqp://guest:guest@localhost:5672//'

CELERY_IMPORTS = ('retarget-service')

CELERY_RESULT_BACKEND = 'amqp'
CELERY_TASK_RESULT_EXPIRES = 18000

CELERYBEAT_SCHEDULE = {
    'clean-generated-every-three-hours': {
        'task': 'retarget-service.clean_generated',
        'schedule': timedelta(hours=1)
    }
}
