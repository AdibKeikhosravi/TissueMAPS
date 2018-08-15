% Copyright 2016 Markus D. Herrmann, University of Zurich
% 
% Licensed under the Apache License, Version 2.0 (the "License");
% you may not use this file except in compliance with the License.
% You may obtain a copy of the License at
% 
%     http://www.apache.org/licenses/LICENSE-2.0
% 
% Unless required by applicable law or agreed to in writing, software
% distributed under the License is distributed on an "AS IS" BASIS,
% WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
% See the License for the specific language governing permissions and
% limitations under the License.
function figure = plotlygetfile(file_owner, file_id)

    [un, key, domain] = signin;

    headers = struct(...
                    'name',...
                        {...
                            'plotly-username',...
                            'plotly-apikey',...
                            'plotly-version',...
                            'plotly-platform',...
                            'user-agent'
                        },...
                    'value',...
                        {...
                            un,...
                            key,...
                            plotly_version,...
                            'MATLAB',...
                            'MATLAB'
                        });

    url = [domain, '/apigetfile/', file_owner, '/', num2str(file_id)];

    [response_string, extras] = urlread2(url, 'Post', '', headers);
    response_handler(response_string, extras);
    response_object = loadjson(response_string);
    figure = response_object.payload.figure;
end
