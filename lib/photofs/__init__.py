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
import subprocess
import sys
import time

# For FUSE
import errno
import fuse

# For guessing whether a file is an image or a video when the source does not
# know
import mimetypes

from xdg.BaseDirectory import xdg_config_dirs, xdg_data_dirs


# Give the user a warning if sqlite cannot be imported
try:
    import sqlite3
except ImportError:
    print('This program requires sqlite3')
    sys.exit(1)


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
    def path(self):
        """The full path of this tag. This is an absolute path."""
        return os.path.sep.join((self._parent.path, self._name)) \
            if self._parent else os.path.sep + self._name

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

    def _default_location(self):
        """Returns the default location of the backend resource.

        :return: the default location of the backend resource, or ``None`` if
            none exists
        :rtype: str or None
        """
        raise NotImplementedError()

    def _load_tags(self):
        """Loads the tags from the backend resource.

        This function is called by refresh if the timestamp of the backend
        resource has changed.

        :return: a list of tags with the images attached
        :rtype: [Tag]
        """
        raise NotImplementedError()

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

    def __init__(self, path = None, date_format = '%Y-%m-%d, %H.%M', **kwargs):
        """Creates a new ImageSource.

        :param str path: The path to the backend database or directory for this
            image source. If :meth:`refresh` is not overloaded, this must be a
            valid file name. Its timestamp is used to determine whether to
            actually reload all images and tags. If this is not provided, a
            default location is used.

        :param str date_format: The date format to use when creating file names
            for images that do not have a title.
        """
        super(ImageSource, self).__init__()
        self._path = path or self._default_location()
        if self._path is None:
            raise ValueError('No database')
        self._date_format = date_format
        self._timestamp = 0

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

        In this case, the internal timestamp is updated and :meth:`_load_tags`
        is called.
        """
        # Check the timestamp
        if self._path:
            timestamp = os.stat(self._path).st_mtime
            if timestamp == self._timestamp:
                return
            self._timestamp = timestamp

        # Release the old data and reload the tags
        self.clear()
        self._load_tags()

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


@ImageSource.register('shotwell')
class ShotwellSource(ImageSource):
    """Loads images and videos from Shotwell.
    """
    def _default_location(self):
        """Determines the location of the *Shotwell* database.

        :return: the location of the database, or ``None`` if it cannot be
            located
        :rtype: str or None
        """
        for d in xdg_data_dirs:
            result = os.path.join(d, 'shotwell', 'data', 'photo.db')
            if os.access(result, os.R_OK):
                return result

    def _load_tags(self):
        db = sqlite3.connect(self._path)
        try:
            # The descriptions of the different image tables; the value tuple is
            # the header of the ID in the tag table, the map of IDs to images
            # and whether the table contains videos
            db_tables = {
                'phototable': ('thumb', {}, False),
                'videotable': ('video-', {}, True)}

            # Load the images
            for table_name, (header, images, is_video) in db_tables.items():
                results = db.execute("""
                    SELECT id, filename, exposure_time, title
                        FROM %s""" % table_name)
                for r_id, r_filename, r_exposure_time, r_title in results:
                    # Make sure the title is set to a reasonable value
                    if not r_title:
                        r_title = time.strftime(self._date_format,
                            time.localtime(r_exposure_time))

                    images[r_id] = Image(
                        r_filename,
                        int(r_exposure_time),
                        r_title,
                        is_video)

            # Load the tags
            results = db.execute("""
                SELECT name, photo_id_list
                    FROM tagtable
                    ORDER BY name""")
            for r_name, r_photo_id_list in results:
                # Ignore unused tags
                if not r_photo_id_list:
                    continue

                # Hierachial tag names start with '/'
                path = r_name.split('/') if r_name[0] == '/' else ['', r_name]
                path_name = os.path.sep.join(path)

                # Make sure that the tag and all its parents exist
                tag = self._make_tags(path_name)

                # The IDs are all in the text of photo_id_list, separated by
                # commas; there is an extra comma at the end
                ids = r_photo_id_list.split(',')[:-1]

                # Iterate over all image IDs and move them to this tag
                for i in ids:
                    if i[0].isdigit():
                        # If the first character is a digit, this is a legacy
                        # source ID and an ID in the photo table
                        image = db_tables['phototable'][1].get(int(i))
                    else:
                        # Iterate over all database tables and locate the image
                        # instance for the current ID
                        image = None
                        for table_name, (header, images, is_video) \
                                in db_tables.items():
                            if not i.startswith(header):
                                continue
                            image = images.get(int(i[len(header):], 16))
                            break

                    # Verify that the tag only references existing images
                    if image is None:
                        continue

                    # Remove the image from the parent tags
                    parent = tag.parent
                    while parent:
                        for k, v in parent.items():
                            if v == image:
                                del parent[k]
                        parent = parent.parent

                    # Finally add the image to this tag
                    tag.add(image)

        finally:
            db.close()


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

    :param sync_to: A file to which to copy the database used when changes are
        detected.
    :type sync_to: str or None

    :raises RuntimeError: if an error occurs
    """
    def __init__(self,
            source = list(ImageSource.SOURCES.keys())[0],
            database = None,
            photo_path = 'Photos',
            video_path = 'Videos',
            date_format = '%Y-%m-%d, %H.%M',
            sync_to = None):
        super(PhotoFS, self).__init__()

        self._sync = None

        self.source = source
        self.database = database
        self.photo_path = photo_path
        self.video_path = video_path
        self.date_format = date_format
        self.sync_to = sync_to

        self.creation = None
        self.dirstat = None
        self.image_source = None
        self.resolvers = {}

        # Create the image source
        self.image_source = ImageSource.get(self.source)(
            self.database, self.date_format)

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

            # Use the lstat result of the database directory for all directories
            self.dirstat = os.lstat(os.path.dirname(self.image_source.path))

        except Exception as e:
            try:
                raise RuntimeError('Failed to initialise file system: %s',
                    e.args[0] % e.args[1:])
            except:
                raise RuntimeError('Failed to initialise file system: %s',
                    str(e))

        else:
            if self.sync_to:
                # If a sync_to argument has been provided, we make sure that
                # file is kept up-to-date with the actual database
                self.sync_start(self.image_source.path, self.sync_to)

    def destroy(self, path):
        self.sync_stop()

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

            self.fs.image_source.refresh()

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
            self.fs.image_source.refresh()
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
            self.fs.image_source.refresh()
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

    def sync_stop(self):
        """Stops the external process responsible for syncing the database
        files.

        If no external process is running, no action is taken.
        """
        if self._sync:
            self._sync.kill()
            self._sync = None

    def sync_start(self, source, target, remove_target = False):
        """Starts an external process to sync ``source`` and ``target``.

        The process will make sure that any time ``source`` is changed, its
        content and attributes will be copied to ``target``.

        The external process will have copied ``source`` to ``target`` before
        this method returns.

        :param str source: The source file.

        :param str target: The target file.

        :param bool remove_target: If ``True``, the target file will be removed
            when :meth:`sync_stop` is called.

        :raises OSError: if the program ``photofs-sync-db`` is not available on
            the system

        :raises RuntimeError: if the sync script exits within one second
        """
        # Make sure no sync process is running
        self.sync_stop()

        # Execute the sync process and read the first line printed
        sync = subprocess.Popen(
            ['photofs-sync-db',
                source,
                target,
                'cleanup' if remove_target else 'none'],
            stdout = subprocess.PIPE)
        line = sync.stdout.readline()

        code = sync.poll()
        if not code is None:
            raise RuntimeError('Failed to execute sync script: %s', line)

        self._sync = sync

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
        self.image_source.refresh()
        try:
            root, rest = self.split_path(path)

            # A call to readlink may only happen on an item in a resolver
            try:
                item = self.image_source.locate(os.path.sep + rest)

                if isinstance(item, Image):
                    # This is a file
                    return item.location

                else:
                    raise RuntimeError('Unknown object: %s',
                        os.path.sep.join(root, path))

            except KeyError:
                raise fuse.FuseOSError(errno.ENOENT)

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

        except OSError as e:
            raise fuse.FuseOSError(e.errno)

    def open(self, path, flags):
        return os.open(self.readlink(path), flags)

    def release(self, path, fh):
        try:
            os.close(fh)
        except:
            raise fuse.FuseOSError(errno.EINVAL)

    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, 0)
        return os.read(fh, size)
