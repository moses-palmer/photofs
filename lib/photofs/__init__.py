#!/usr/bin/env python
# coding: utf-8
# photofs
# Copyright (C) 2012-2016 Moses Palmér
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

import os
import stat
import threading
import time

# For FUSE
import errno
import fuse

from ._image import Image, FileBasedImage
from ._source import ImageSource
from ._tag import Tag


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

    :param bool use_links: Whether to report file based images as links.

    :param dict filters: A mapping from top level directory to filtering
        function. If this is falsy, no filters are used, and root tags are used
        to populate the root directory.

    :param str video_path: The directory in the mounted root to contain videos.

    :param str date_format: The date format string used to construct file names
        from time stamps.

    :raises RuntimeError: if an error occurs
    """

    def __init__(
            self,
            mountpoint,
            source=list(ImageSource.SOURCES.keys())[0],
            use_links=False,
            filters={},
            date_format='%Y-%m-%d, %H.%M',
            **kwargs):
        super(PhotoFS, self).__init__()

        self.source = source
        self.use_links = use_links
        self.filters = filters
        Image.DATE_FORMAT = date_format

        self.creation = None
        self.dirstat = None
        self.image_source = None

        self.handles = {}

        # Create the image source
        self.image_source = ImageSource.get(self.source)(**kwargs)

        try:
            # Store the current time as timestamp for directories
            self.creation = int(time.time())

            # Use the lstat result of the mount point for all directories
            self.dirstat = os.lstat(mountpoint)

        except Exception as e:
            try:
                raise RuntimeError(
                    'Failed to initialise file system: %s',
                    e.args[0] % e.args[1:])
            except:
                raise RuntimeError(
                    'Failed to initialise file system: %s',
                    str(e))

    def destroy(self, path):
        pass

    def recursive_filter(self, item, include):
        """The recursive filter used to actually filter the image source.

        This function will simply call include_filter in the outer scope if
        item is an instance of :class:`Image`, otherwise it will recursively
        call itself on all items in the tag, and return whether the filtered
        tag contains any subitems.

        :param item: The item to filter.
        :type item: Image or Tag

        :return: ``True`` if the item should be kept and ``False``
            otherwise
        """
        if isinstance(item, Image):
            return include(item)
        elif isinstance(item, Tag):
            return any(
                self.recursive_filter(item, include)
                for item in item.values())
        else:
            return False

    def locate(self, path):
        """Locates a filter function and an image or tag resource.

        If the path denotes the root, :attr:`self.image_source` is returned

        :param str path: The absolute path of the resource. This must begin
            with :attr:`os.path.sep`.

        :return: the tuple ``(include, resource)``, where ``include`` is
            ``None`` if no filters are registered

        :raises KeyError: if the resource does not exist using the filter
        """
        # The root path corresponds to the filters, if any registered, or the
        # image source root tags
        if path == os.path.sep:
            return (None, self.filters or self.image_source)

        # If any filters are registered, the first part of the path is the
        # filter name; the filter must allow the item
        if self.filters:
            root, rest = self.split_path(path)
            include = self.filters[root]
            if rest:
                item = self.image_source.locate(os.path.sep + rest)
                if not self.recursive_filter(item, include):
                    raise KeyError(path)
            path = os.path.sep + rest
        else:
            include = None

        return (
            include,
            self.image_source.locate(path) if path else self.image_source)

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
            raise ValueError(
                '%s is not a valid path',
                path)
        path = path[len(os.path.sep):]

        if os.path.sep in path:
            return path.split(os.path.sep, 1)
        else:
            return (path, '')

    def getattr(self, path, fh=None):
        try:
            include, item = self.locate(path)

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

        if self.use_links and isinstance(item, FileBasedImage):
            # This is a link
            st = os.stat_result((item.stat[0] | stat.S_IFLNK,) + item.stat[1:])

        elif isinstance(item, Image):
            # This is a file
            st = item.stat

        elif isinstance(item, dict):
            # This is a directory; this matches both Tag and ImageSource
            st = self.dirstat

        else:
            raise RuntimeError(
                'Unknown object: %s',
                path)

        return dict(
            # Remove write permission bits
            st_mode=st.st_mode & ~(
                stat.S_IWGRP | stat.S_IWUSR | stat.S_IWOTH),

            st_gid=st.st_gid,
            st_uid=st.st_uid,

            st_nlink=st.st_nlink,

            st_atime=st.st_atime,
            st_ctime=st.st_ctime,
            st_mtime=st.st_mtime,

            st_size=st.st_size)

    def readdir(self, path, offset):
        if path == os.path.sep:
            return [
                k
                for k in (self.filters or self.image_source)]

        try:
            include, item = self.locate(path)

        except KeyError:
            raise fuse.FuseOSError(errno.ENOENT)

        if isinstance(item, dict):
            # This is a directory; this matches both Tag and
            # ImageSource
            return [
                k
                for k, v in item.items()
                if self.recursive_filter(v, include)]

        else:
            raise RuntimeError(
                'Unknown object: %s',
                os.path.join(root, path))

    def readlink(self, path):
        include, item = self.locate(path)
        try:
            return item.location
        except:
            raise fuse.FuseOSError(errno.EINVAL)

    def open(self, path, flags):
        include, item = self.locate(path)
        if isinstance(item, Image):
            handle = item.open(flags)
            self.handles[id(handle)] = (handle, threading.Lock())
            return id(handle)
        else:
            raise fuse.FuseOSError(errno.EINVAL)

    def release(self, path, fh):
        try:
            handle, lock = self.handles[fh]
            with lock:
                handle.close()
            del self.handles[fh]
        except:
            raise fuse.FuseOSError(errno.EINVAL)

    def read(self, path, size, offset, fh):
        handle, lock = self.handles[fh]
        with lock:
            if handle.tell() != offset:
                handle.seek(offset)
            return handle.read(size)
