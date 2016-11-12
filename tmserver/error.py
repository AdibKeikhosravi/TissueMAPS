# TmServer - TissueMAPS server application.
# Copyright (C) 2016  Markus D. Herrmann, University of Zurich and Robin Hafen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Custom exception types and associated serializers.
When raised these exceptions will be automatically handled and serialized by
the flask error handler and sent to the client.

"""
import logging
import importlib
import inspect
import sqlalchemy

from tmserver.serialize import json_encoder

logger = logging.getLogger(__name__)


class HTTPException(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self.message)


@json_encoder(HTTPException)
def encode_api_exception(obj, encoder):
    return {
        'error': True,
        'message': obj.message,
        'status_code': obj.status_code,
        'type': obj.__class__.__name__
    }


class MalformedRequestError(HTTPException):

    default_message = 'Invalid request.'

    def __init__(self, message=default_message):
        super(MalformedRequestError, self).__init__(
            message=message, status_code=400
        )


class MissingGETParameterError(MalformedRequestError):

    def __init__(self, *parameters):
        super(MissingGETParameterError, self).__init__(
            message=(
                'The following GET parameters are required but were missing'
                ' in the request: "%s".' % '", "'.join(parameters)
            )
        )


class MissingPOSTParameterError(MalformedRequestError):

    def __init__(self, *parameters):
        super(MissingPOSTParameterError, self).__init__(
            message=(
                'The following POST parameters are required but were missing'
                ' in the request body: "%s".' % '", "'.join(parameters)
            )
        )


class NotAuthorizedError(HTTPException):

    default_message = 'This user does not have access to the requested resource.'

    def __init__(self, message=default_message):
        super(NotAuthorizedError, self).__init__(
            message=message, status_code=401
        )


class ResourceNotFoundError(HTTPException):

    def __init__(self, model, **parameters):
        if parameters:
            message = (
                'The requested resource of type "%s" was not found '
                'for parameters: %s' % (
                    model.__name__,
                    ', '.join([
                        '='.join([k, v]) for k, v in parameters.iteritems()
                    ])
                )
            )
        else:
            message = (
                'The requested resource of type "%s" was not found.' %
                model.__name__
            )
        super(ResourceNotFoundError, self).__init__(
            message=message, status_code=404
        )


class InternalServerError(HTTPException):

    default_message = 'The server encountered an unexpected problem.'

    def __init__(self, message=default_message):
        super(InternalServerError, self).__init__(
            message=message, status_code=500
        )


def register_http_error_classes(error_handler_func):
    """Registers an error handler for error classes derived from
    :class:`HTTPException <tmserver.error.HTTPException>`.

    Parameters
    ----------
    error_handler_func: function
    """
    module = importlib.import_module('tmserver.error')
    HTTPException = getattr(module, 'HTTPException')
    for name, obj in inspect.getmembers(module):
    # for name, obj in inspect.getmembers(globals()):
        if inspect.isclass(obj):
            if HTTPException in inspect.getmro(obj):
                logger.debug('mokey path class %r with error handler', obj)
                globals()[obj.__name__] = error_handler_func(obj)
