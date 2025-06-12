"""Common utility functions and custom exceptions for the application.

This module provides helper functions that are used across various
parts of the application, such as file reading utilities.
"""
import types
import inspect
import typing
# import os
# import appdirs # You might need to add appdirs to requirements.txt

# class Commons:
#     APP_NAME = "ChatApp" # Or your application's name
#     APP_AUTHOR = "YourAppNameOrAuthor" # Or your application's author/org

#     @staticmethod
#     def get_data_dir() -> str:
#         """
#         Returns the application's user-specific data directory.
#         Creates the directory if it doesn't exist.
#         """
#         data_dir = appdirs.user_data_dir(Commons.APP_NAME, Commons.APP_AUTHOR)
#         os.makedirs(data_dir, exist_ok=True)
#         return data_dir

def read_str(filepath : str) -> str:
    """Reads the content of a file and returns it as a string.

    Args:
        filepath (str): The path to the file.
        
    Returns:
        str: The content of the file as a string.
    """
    with open(filepath, 'r', encoding='utf-8') as file:
        return file.read().strip()

# def to_obj(data: typing.Any, cls: type) -> object:
#     """
#     Converts input data to an object of the specified class type.
#     This function supports basic types (str, int, float, bool), generic
#     """
#     if data is None:
#         return None

#     if type(cls) is str:
#         if cls == "str":
#             cls = str
#         elif cls == "int":
#             cls = int
#         elif cls == "float":
#             cls = float
#         elif cls == "bool":
#             cls = bool
#         else:
#             assert False, f"Unsupported type string {cls} for input {data} of type {type(data)}"

#     if cls in (str, int, float, bool):
#         assert isinstance(data, cls), f"Expected {cls.__name__}, got {type(data).__name__}"
#         return data

#     if isinstance(cls, types.GenericAlias):
#         if cls.__origin__ is list:
#             assert isinstance(data, list), f"Expected list, got {type(data).__name__}"
#             return [to_obj(item, cls.__args__[0]) for item in data]
#         elif cls.__origin__ is dict:
#             assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"
#             assert cls.__args__[0] in (str, int), "Dictionary keys must be str or int"
#             if cls.__args__[0] is str:
#                 assert all(isinstance(key, str) for key in data.keys()), "All keys must be strings"
#             elif cls.__args__[0] is int:
#                 assert all(isinstance(key, int) for key in data.keys()), "All keys must be integers"
#             return {key: to_obj(value, cls.__args__[1]) for key, value in data.items()}
#         assert False, f"Unsupported generic type {cls}"
#     if inspect.isclass(cls):
#         assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"
#         init_dict = {}
#         for attrname, field in cls.__dataclass_fields__.items():
#             print(field)
#             assert field.type is not None, f"Field {attrname} in {cls.__name__} has no type annotation"
#             if attrname not in data:
#                 if field.default is not None:
#                     init_dict[attrname] = field.default
#                 elif field.default_factory is not None:
#                     init_dict[attrname] = field.default_factory()
#                 else:
#                     init_dict[attrname] = None
#                 continue
#             init_dict[attrname] = to_obj(data[attrname], field.type)
#         return cls(**init_dict)
#     assert False, f"Unsupported type {cls} for input {data} of type {type(data)}"
