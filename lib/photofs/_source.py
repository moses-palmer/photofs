#!/usr/bin/env python
# coding: utf-8
# photofs
# Copyright (C) 2012-2014 Moses Palmér
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

import os

from ._util import make_unique
from ._image import Image
from ._tag import Tag


class ImageSource(dict):
    """A source of images and tags.

    This is an abstract class.
    """
    #: A mapping of all registered sources by name to implementing classes
    SOURCES = {}

    @classmethod
    def add_arguments(self, argparser):
        """Adds all command line arguments for this image source to an argument
        parser.

        :param argparse.ArgumentParser argparser: The argument parser to which
            to add arguments.
        """
        pass

    @classmethod
    def register(self, name):
        """A decorator that registers an :class:`ImageSource` subclass as an
        image source.

        :param str name: The name of the image source.
        """
        def inner(cls):
            self.SOURCES[name] = cls
            return cls
        return inner

    @classmethod
    def get(self, name):
        """Returns the class responsible for a named image source.

        :param str name: The name of the source.

        :return: the corresponding class

        :raises ValueError: if ``name`` is not a known image source
        """
        try:
            return self.SOURCES[name]
        except KeyError:
            raise ValueError('%s is not a valid image source', name)

    def _break_path(self, path):
        """Breaks an absolute path into its segments.

        :param str path: The absolute path to break, for example
            ``'/Tag/Other/Third'``, which will yield
            ``['Tag', 'Other', 'Third']``. This string must begin with
            :attr:`os.path.sep`.

        :raises ValueError: if path does not begin with os.path.sep

        :return: the path elements
        :rtype: [str]
        """
        # Make sure the path begins with a path separator
        if path[0] != os.path.sep:
            raise ValueError('"%s" does not begin with "%s"',
                path,
                os.path.sep)
        elif path == os.path.sep:
            return []

        return path.split(os.path.sep)[1:]

    def _make_unique(self, directory, base_name, ext):
        """Creates a unique key in the map ``directory``.

        See :func:`make_unique` for more information.

        :param dict directory: The map in which to create the unique key.

        :param str base_name: The name of the file without extension.

        :param str ext: The file extension. A dot (``'.'``) is not added
            automatically; this must be present in ``ext``.

        :return: a unique key
        :rtype: str
        """
        return make_unique(directory, base_name, '%s%s', '%s (%d)%s', ext)

    def _make_tags(self, path):
        """Makes sure that all tags up until the last element of ``path`` exist.

        :param str path: The absolute path of the tag to make, for example
            ``'/Tag/Other/Third'``. This string must begin with
            :attr:`os.path.sep`.

        :raises ValueError: if ``path`` does not begin with :attr:`os.path.sep`

        :return: the last tag; ``Third`` in the example above
        :rtype: Tag
        """
        segments = self._break_path(path)

        # Create all tags
        current = self
        for segment in segments:
            if not segment in current:
                tag = Tag(segment, current if current != self else None)
                if current == self:
                    # If the tag does not exist, and this is a root tag
                    # (current == self => this is the first iteration), add the
                    # tag to self; the parent parameter to Tag above will handle
                    # other cases
                    self[segment] = tag
            current = current[segment]

        return current

    def __init__(self, **kwargs):
        """Creates a new ImageSource.

        :param str date_format: The date format to use when creating file names
            for images that do not have a title.
        """
        if kwargs:
            raise ValueError('Unsupported command line argument: %s',
                ', '.join(k for k in kwargs))
        super(ImageSource, self).__init__()

    def locate(self, path):
        """Locates an image or tag.

        :param str path: The absolute path of the item to locate, for example
            ``'/Tag/Other/Image.jpg'``. This string must begin with
            :attr:`os.path.sep`.

        :return: a tag or an image
        :rtype: Tag or Image

        :raises KeyError: if the item does not exist

        :raises ValueError: if path does not begin with os.path.sep
        """
        segments = self._break_path(path)

        # Locate the last item
        current = self
        for segment in segments:
            current = current[segment]

        return current


class FileBasedImageSource(ImageSource):
    """A source of images and tags where the backend is file based.

    This is an abstract class.
    """
    @classmethod
    def add_arguments(self, argparser):
        """Adds all command line arguments for this image source to an argument
        parser.

        :param argparse.ArgumentParser argparser: The argument parser to which
            to add arguments.
        """
        argparser.add_argument('--database', help =
            'The database file to use. If not specified, the default one is '
            'used.')

    def __init__(self, database = None, **kwargs):
        """Creates a new ImageSource.

        :param str database: The path to the backend database or directory for
            this image source. If :meth:`refresh` is not overloaded, this must
            be a valid file name. Its timestamp is used to determine whether to
            actually reload all images and tags. If this is not provided, a
            default location is used.
        """
        super(FileBasedImageSource, self).__init__(**kwargs)
        self._path = database or self.default_location
        if self._path is None:
            raise ValueError('No database')
        self._timestamp = 0

    def load_tags(self):
        """Loads the tags from the backend resource.

        This function is called by refresh if the timestamp of the backend
        resource has changed.

        :return: a list of tags with the images attached
        :rtype: [Tag]
        """
        raise NotImplementedError()

    @property
    def default_location(self):
        """Returns the default location of the backend resource.

        :return: the default location of the backend resource, or ``None`` if
            none exists
        :rtype: str or None
        """
        raise NotImplementedError()

    @property
    def path(self):
        """The path of the backend resource containing the images and tags."""
        return self._path

    @property
    def timestamp(self):
        """The timestamp when the backend resource was last modified."""
        return self._timestamp

    def refresh(self):
        """Reloads all images and tags from the backend resource if it has
        changed since the last update.

        If the last modification time of :attr:`path` has changed, the backend
        resource is considered to be changed as well.

        In this case, the internal timestamp is updated and :meth:`load_tags`
        is called.
        """
        # Check the timestamp
        if self.path:
            timestamp = os.stat(self._path).st_mtime
            if timestamp == self._timestamp:
                return
            self._timestamp = timestamp

        # Release the old data and reload the tags
        self.clear()
        self.load_tags()

    def locate(self, path):
        self.refresh()
        return super(FileBasedImageSource, self).locate(path)
