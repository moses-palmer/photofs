def _names():
    """Lists the names of all resources in this package.

    :return: the names of all resources
    :rtype: [str]
    """
    import os
    import pkg_resources

    return (None
        or pkg_resources.resource_listdir('photofs', 'sources')
        or os.listdir(os.path.dirname(__file__)))

__all__ = [name.rsplit('.', 1)[0]
    for name in _names()
    if name.endswith('.py') and not name[0] == '_']
