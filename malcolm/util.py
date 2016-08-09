import os
import importlib
import logging


def import_methodmeta_decorated_classes(globals_d, *package_path):
    """Prepare a package namespace by importing all subclasses following PEP8
    rules that have @takes decorated functions"""
    class_dict = {}
    # this is the path to the package
    package_fs_path = os.path.join(os.path.dirname(__file__), *package_path)
    for f in os.listdir(package_fs_path):
        if f.endswith(".py") and f != "__init__.py":
            # import it and see what it produces
            import_name = "malcolm.%s.%s" % (".".join(package_path), f[:-3])
            logging.debug("Importing %s" % import_name)
            module = importlib.import_module(import_name)
            for cls in find_decorated_classes(module):
                class_dict[cls.__name__] = cls

    globals_d.update(class_dict)
    __all__ = list(class_dict)
    return __all__


def import_sub_packages(globals_d, *package_path):
    module_dict = {}
    # this is the path to the package
    package_fs_path = os.path.join(os.path.dirname(__file__), *package_path)
    for f in os.listdir(package_fs_path):
        if os.path.isdir(f):
            # import it and add it to the list
            import_name = "malcolm.%s" % (".".join(package_path),)
            logging.debug("Importing %s" % import_name)
            module = importlib.import_module(import_name)
            module_dict[f] = module

    globals_d.update(module_dict)
    __all__ = list(module_dict)
    return __all__



def find_decorated_classes(module):
    for n in dir(module):
        cls = getattr(module, n)
        if hasattr(cls, "MethodMeta"):
            module_name = module.__name__.split(".")[-1]
            if n.lower() != module_name:
                logging.warning("Classname %s when lower cased should be %s" %
                                (n, module_name))
            logging.debug("Found child class %s" % cls)
            yield cls
