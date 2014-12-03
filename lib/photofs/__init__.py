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
import stat
import sys
import time

# For FUSE
import errno
import fuse

# For guessing whether a file is an image or a video when the source does not
# know
import mimetypes


def make_unique(mapping, base_name, format_1, format_n, *args):
    """Creates a unique key in a ``dict``.

    First the string ``format_1 % base_name`` is tried. If that is present in
    ``mapping``, the strings ``format_n % ((base_name, n) + args)`` with ``n``
    incrementing from ``2`` are tried until a unique one is found.

    :param str base_name: The name of the file without extension.

    :param str format_1: The initial format string. This will be passed
        ``base_name`` followed by ``args``.

    :param str format_n: The fallback format string. This will be passed
        ``base_name`` followed by an index and then ``args``.

    :param args: Format string arguments used.

    :return: a unique key
    :rtype: str
    """
    i = 1
    key = format_1 % ((base_name,) + args)
    while key in mapping:
        i += 1
        key = format_n % ((base_name, i) + args)

    return key


class Image(object):
    """An image or video.
    """
    def __init__(self, location, timestamp, title, is_video = None):
        """
        Initialises an image.

        :param str location: The location of this image in the file system.

        :param int timestamp: The timestamp when this image or video was
            created.

        :param str title: The title of the image. This should be used to
            generate the file name. If the ``title`` is empty or ``None``,
            ``timestamp`` should be used instead.

        :param bool is_video: Whether this image is a video. This must be either
            ``True`` or ``False``, or ``None``. If it is ``None``, the type is
            inferred from the file *MIME type*.
        """
        super(Image, self).__init__()
        self._location = location
        self._timestamp = timestamp
        self._title = title
        if is_video is None:
            mime, encoding = mimetypes.guess_type(location)
            self._is_video = mime and mime.startswith('video/')
        else:
            self._is_video = is_video

    @property
    def location(self):
        """The location of this image or video in the file system."""
        return self._location

    @property
    def timestamp(self):
        """The timestamp when this image or video was created."""
        return self._timestamp

    @property
    def title(self):
        """The title of this image. Use this to generate the file name if it is
        set."""
        return self._title

    @property
    def is_video(self):
        """Whether this image is a video."""
        return self._is_video


class Tag(dict):
    """A tag applied to an image or a video.

    An image or video may have several tags applied. In that case an image with
    the same location will be present in the image collection of several tags.
    The image references may not be equal.

    Tags are hierarchial. A tag may have zero or one parent, and any number of
    children. The parent-child relationship is noted in the name of tags: the
    name of a tag will be ``<name of grandparents..>/<name of parent>/<name>``.
    """

    def _make_unique(self, base_name, ext):
        """Creates a unique key in this dict.

        See :func:`make_unique` for more information.

        :param str base_name: The name of the file without extension.

        :param str ext: The file extension. A dot (``'.'``) is not added
            automatically; this must be present in ``ext``.

        :return: a unique key
        :rtype: str
        """
        return make_unique(self, base_name, '%s%s', '%s (%d)%s', ext)

    def __setitem__(self, k, v):
        # Make sure keys are strings and items are images or tags
        if not isinstance(k, str) and not (False
                or isinstance(v, Image)
                or isinstance(v, Tag)):
            raise ValueError('Cannot add %s to Tag',
                str(v))

        super(Tag, self).__setitem__(k, v)

    def __init__(self, name, parent = None):
        """Initialises a named tag.

        :param str name: The name of the tag.

        :param Tag parent: The parent tag. This is used to create the full name
            of the tag. If this is ``None``, a root tag is created, otherwise
            this tag is added to the parent tag.
        """
        super(Tag, self).__init__()
        self._name = name
        self._parent = parent

        # Make sure to add ourselves to the parent tag if specified
        if parent:
            parent.add(self)

        self._has_video = False
        self._has_image = False

    @property
    def name(self):
        """The name of this tag."""
        return self._name

    @property
    def parent(self):
        """The parent of this tag."""
        return self._parent

    @property
    def has_image(self):
        """Whether this tag contains at least one image"""
        return self._has_image

    @property
    def has_video(self):
        """Whether this tag contains at least one video"""
        return self._has_video

    def add(self, item):
        """Adds an image or tag to this tag.

        If a tag is added, it will be stored with the key ``item.name``. If this
        key already has a value, the following action is taken:

        - If the value is a tag, the new tag overwrites it.
        - If the value is an image, a new unique name is generated and the
          image is moved.

        :param item:
            An image or a tag.
        :type item: Image or Tag

        :raises ValueError: if item is not an instance of :class:`Image` or
            :class:`Tag`
        """
        if isinstance(item, Image):
            name, ext = os.path.splitext(item.location)

            # Make sure the key name is unique
            key = self._make_unique(item.title, ext.lower())
            self[key] = item

            self._has_image = self._has_image or not item.is_video
            self._has_video = self._has_image or item.is_video

        elif isinstance(item, Tag):
            previous = self.get(item.name)
            self[item.name] = item

            # Re-add the previous item if it was an image
            if isinstance(previous, Image):
                self.add(previous)

            self._has_image = self._has_image or item.has_video
            self._has_video = self._has_image or item.has_image

        else:
            raise ValueError('Cannot add %s to a Tag',
                str(item))


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

    def __init__(self, date_format = '%Y-%m-%d, %H.%M', **kwargs):
        """Creates a new ImageSource.

        :param str date_format: The date format to use when creating file names
            for images that do not have a title.
        """
        if kwargs:
            raise ValueError('Unsupported command line argument: %s',
                ', '.join(k for k in kwargs))
        super(ImageSource, self).__init__()
        self._date_format = date_format

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


# Import the actual image sources
from .sources import *


class PhotoFS(fuse.LoggingMixIn, fuse.Operations):
    """An implementation of a *FUSE* file system.

    It presents the tagged image libraries from image sources as a tag tree in
    the file system.

    :param ImageSource source: The image source.

    :param database: An override for the default database file for the
        selected image source.
    :type database: str or None

    :param str photo_path: The directory in the mounted root to contain photos.

    :param str video_path: The directory in the mounted root to contain videos.

    :param str date_format: The date format string used to construct file names
        from time stamps.

    :raises RuntimeError: if an error occurs
    """
    def __init__(self,
            mountpoint,
            source = list(ImageSource.SOURCES.keys())[0],
            photo_path = 'Photos',
            video_path = 'Videos',
            date_format = '%Y-%m-%d, %H.%M',
            **kwargs):
        super(PhotoFS, self).__init__()

        self.source = source
        self.photo_path = photo_path
        self.video_path = video_path
        self.date_format = date_format

        self.creation = None
        self.dirstat = None
        self.image_source = None
        self.resolvers = {}

        # Create the image source
        self.image_source = ImageSource.get(self.source)(
            date_format = self.date_format, **kwargs)

        try:
            # Make sure the photo and video paths are strs
            self.photo_path = str(self.photo_path)
            self.video_path = str(self.video_path)

            # Load the photo and video resolvers
            self.resolvers = {
                self.photo_path: self.ImageResolver(self,
                    lambda i: not i.is_video
                        if isinstance(i, Image)
                        else not i.has_video),
                self.video_path: self.ImageResolver(self,
                    lambda i: i.is_video
                        if isinstance(i, Image)
                        else i.has_video)}

            # Store the current time as timestamp for directories
            self.creation = int(time.time())

            # Use the lstat result of the mount point for all directories
            self.dirstat = os.lstat(mountpoint)

        except Exception as e:
            try:
                raise RuntimeError('Failed to initialise file system: %s',
                    e.args[0] % e.args[1:])
            except:
                raise RuntimeError('Failed to initialise file system: %s',
                    str(e))

    def __getitem__(self, path):
        """Reads the item at ``path``.

        The root component of the path is discarded.

        :param str path: The path for which to find the item.

        :returns: the tag or image
        :rtype: Tag or Image
        """
        self.image_source.refresh()
        root, rest = self.split_path(path)
        return self.image_source.locate(os.path.sep + rest)

    def destroy(self, path):
        pass

    class ImageResolver(object):
        """This class resolves image requests.
        """
        def __init__(self, file_system, include_filter):
            """Creates an image resolver for a specific source and filter.

            :param PhotoFS file_system: The photofs instance.

            :param include_filter: The filter function to apply to images. This
                function will only be passed instances of :class:`Image`.
                :class:`Tag` instances which contain no unfiltered images or
                subtags will automatically be filtered out.
            """
            def recursive_filter(item):
                """The recursive filter used to actually filter the image
                source.

                This function will simply call include_filter in the outer scope
                if item is an instance of :class:`Image`, otherwise it will
                recursively call itself on all items in the tag, and return
                whether the filtered tag contains any subitems.

                :param item: The item to filter.
                :type item: Image or Tag

                :return: ``True`` if the item should be kept and ``False``
                    otherwise
                """
                if isinstance(item, Image):
                    return include_filter(item)
                elif isinstance(item, Tag):
                    return any(recursive_filter(item)
                        for item in item.values())
                else:
                    return False

            self.fs = file_system
            self._include_filter = recursive_filter

        def getattr(self, root, path):
            """Performs a stat on ``/root/path``.

            :param str root: The first segment of the path, which contains the
                string that caused this resolver to be picked by
                :class:`PhotoFS`.

            :param str path: The path to resolve. This has to begin with
                :attr:`os.path.sep`.

            :return: a :class:`os.stat_result` object for the path
            :rtype: os.stat_result

            :raises fuse.FuseOSError: if an error occurs
            """
            try:
                item = self.fs.image_source.locate(path)

                if isinstance(item, Image):
                    # This is a file
                    return os.lstat(item.location)

                elif isinstance(item, dict):
                    # This is a directory; this matches both Tag and ImageSource
                    return self.fs.dirstat

                else:
                    raise RuntimeError('Unknown object: %s',
                        os.path.sep.join(root, path))

            except KeyError:
                raise fuse.FuseOSError(errno.ENOENT)

        def readdir(self, root, path):
            """Performs a directory listing on ``/root/path``.

            :param str root: The first segment of the path, which contains the
                string that caused this resolver to be picked by
                :class:`PhotoFS`.

            :param str path: The path to resolve. This has to begin with
                :attr:`os.path.sep`, and it must be resolved to a dictionary.

            :return: a sequence of strings describing the directory
            :rtype: [str]

            :raises fuse.FuseOSError: if an error occurs
            """
            try:
                item = self.fs.image_source.locate(path)

                if isinstance(item, dict):
                    # This is a directory; this matches both Tag and ImageSource
                    return [k
                        for k, v in item.items()
                        if self._include_filter(v)]

                else:
                    raise RuntimeError('Unknown object: %s',
                        os.path.join(root, path))

            except KeyError:
                raise fuse.FuseOSError(errno.ENOENT)

    def split_path(self, path):
        """Returns the tuple ``(root, rest)`` for a path, where ``root`` is the
        directory immediately beneath the root and ``rest`` is anything after
        that.

        :param str path: The path to split. This must begin with
            :attr:`os.path.sep`.

        :return: a tuple containing the split path, which may be empty strings

        :raises ValueError: if ``path`` does not begin with :attr:`os.path.sep`
        """
        if path[0] != os.path.sep:
            raise ValueError('%s is not a valid path',
                path)
        path = path[len(os.path.sep):]

        if os.path.sep in path:
            return path.split(os.path.sep, 1)
        else:
            return (path, '')

    def getattr(self, path, fh = None):
        try:
            root, rest = self.split_path(path)

            if not rest:
                # Unless path is the root, it must be in the resolvers; the root
                # and any items directly below it are directories
                if root and not root in self.resolvers:
                    raise fuse.FuseOSError(errno.ENOENT)
                else:
                    st = self.dirstat
            else:
                st = self.resolvers[root].getattr(root, os.path.sep + rest)

            return dict(
                # Remove write permission bits
                st_mode = st.st_mode & ~146,

                st_gid = st.st_gid,
                st_uid = st.st_uid,

                st_nlink = st.st_nlink,

                st_atime = st.st_atime,
                st_ctime = st.st_ctime,
                st_mtime = st.st_mtime,

                st_size = st.st_size)

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

        except OSError as e:
            raise fuse.FuseOSError(e.errno)


    def readdir(self, path, offset):
        try:
            root, rest = self.split_path(path)

            if not root:
                # The root contains the resolver names
                items = [d
                    for d in self.resolvers.keys()]
            else:
                items = self.resolvers[root].readdir(root, os.path.sep + rest)

            # We return tuples instead of strings since fusepy on Python 2.x
            # incorrectly treats unicode as non-string
            return [(i, None, 0)
                for i in items]

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

        except OSError as e:
            raise fuse.FuseOSError(e.errno)

    def readlink(self, path):
        try:
            item = self[path]

            if isinstance(item, Image):
                # This is a file
                return item.location
            else:
                raise RuntimeError('Unknown object: %s',
                    os.path.sep.join(root, path))

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

    def open(self, path, flags):
        item = self[path]
        if isinstance(item, Image):
            return os.open(item.location, flags)
        else:
            raise fuse.FuseOSError(errno.EINVAL)

    def release(self, path, fh):
        try:
            os.close(fh)
        except:
            raise fuse.FuseOSError(errno.EINVAL)

    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, 0)
        return os.read(fh, size)
