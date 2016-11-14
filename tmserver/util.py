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
Various utility functions used by view functions and other parts of the
server application.

"""
import functools
from flask import request, current_app
from flask_jwt import current_identity

import tmlib.models as tm

from tmserver.model import decode_pk
from tmserver.error import (
    MalformedRequestError,
    ResourceNotFoundError,
    NotAuthorizedError,
    MissingGETParameterError,
    MissingPOSTParameterError
)


def assert_query_params(*params):
    """A decorator for GET request functions that asserts that the
    query string contains the required parameters.

    Parameters
    ----------
    *params: List[str]
        names of required parameters

    Raises
    ------
    tmserver.error.MissingGETParameterError
        when a required parameter is missing in the request
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if request.method != 'GET':
                raise ValueError(
                    '"assert_query_params" must decorate GET request functions'
                )
            missing = []
            for p in params:
                if p not in request.args:
                    missing.append(p)
            if missing:
                raise MissingGETParameterError(*missing)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def assert_form_params(*params):
    """A decorator for POST request functions that asserts that the
    form body contains the required parameters.

    Parameters
    ----------
    *params: List[str]
        names of required parameters

    Raises
    ------
    tmserver.error.MissingPOSTParameterError
        when a required parameter is missing in the request
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if request.method != 'POST':
                raise ValueError(
                    '"assert_form_params" must decorate POST request functions'
                )
            data = request.get_json()
            missing = []
            for p in params:
                if data is None:
                    raise MissingPOSTParameterError(*params)
                else:
                    if p not in data:
                        missing.append(p)
            if missing:
                raise MissingPOSTParameterError(*missing)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def decode_form_ids(*model_ids):
    """A decorator that extracts and decodes specified model ids from the POST
    body and inserts them into the argument list of the view function.

    Parameters
    ----------
    model_ids: *str
        encoded model ids

    Returns
    -------
    The wrapped view function.

    Raises
    ------
    MalformedRequestError
        This exception is raised if an id was missing from the request body.

    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            data = request.get_json()
            if not data:
                raise MalformedRequestError(
                    'There was no POST body even though the view was expected '
                    'to receive one.'
                )
            for mid in model_ids:
                if mid not in data.keys():
                    raise MalformedRequestError(
                        'ID "%s" was not in the POST body even though '
                        'the view was expected to receive it.' % mid
                    )
                if not mid.endswith('_id'):
                    raise MalformedRequestError('IDs must end with "_id".')
                encoded_model_id = data.get(mid)
                model_id = decode_pk(encoded_model_id)
                kwargs[mid] = model_id
            return f(*args, **kwargs)
        return wrapped
    return decorator


def decode_query_ids(permission='write'):
    """A decorator that extracts and decodes all model IDs from the URL
    and inserts them into the argument list of the view function.

    Parameters
    ----------
    permission: str, optional
        check whether current user has ``"read"`` or ``"write"`` permissions
        for the requested experiment (default: ``"write"``)

    Returns
    -------
    The wrapped view function.

    Raises
    ------
    MalformedRequestError
        when ``"experiment_id"`` was missing from the URL
    NotAuthorizedError
        when requested experiment does not belong to the user

    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            url_args = request.url_rule.arguments
            if 'experiment_id' not in url_args:
                raise MalformedRequestError(
                    'ID "experiment_id" was not in the URL even though '
                    'the view was expected to receive it.'
                )

            for arg in url_args:
                if arg.endswith('_id'):
                    encoded_model_id = request.view_args.get(arg)
                    model_id = decode_pk(encoded_model_id)
                    kwargs[arg] = model_id
                if arg == 'experiment_id':
                    with tm.utils.MainSession() as session:
                        experiment = session.query(tm.ExperimentReference).\
                            get(model_id)
                        if experiment is None:
                            raise ResourceNotFoundError(
                                tm.Experiment, experiment_id=experiment_id
                            )
                        granted = experiment.can_be_accessed_by(
                            current_identity.id, permission
                        )
                        if not granted:
                            raise NotAuthorizedError(
                                'User is not authorized to access '
                                'experiment #%d.' % model_id
                            )
                            current_identity.id
            return f(*args, **kwargs)
        return wrapped
    return decorator

