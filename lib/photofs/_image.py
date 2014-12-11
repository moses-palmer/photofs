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

import datetime
import mimetypes
import os
import time


class Image(object):
    """An image or video.
    """

    #: The date format used to construct the title when none is set
    DATE_FORMAT = '%Y-%m-%d, %H.%M'

    def __init__(self, title, extension, timestamp, st, is_video = None):
        """Initialises an image.

        :param str title: The title of the image. This should be used to
            generate the file name. If ``title`` is empty or ``None``,
            ``timestamp`` is used instead.

        :param str extension: The file extension.

        :param timestamp: The timestamp when this image or video was
            created.
        :type timestamp: int or datetime.datetime

        :param os.stat_result st: The ``stat`` value for this item.

        :param bool is_video: Whether this image is a video. This must be either
            ``True`` or ``False``, or ``None``. If it is ``None``, the type is
            inferred from the file *MIME type*.
        """
        super(Image, self).__init__()
        self._title = title
        self._extension = extension
        if isinstance(timestamp, datetime.datetime):
            self._timestamp = timestamp
        else:
            self._timestamp = datetime.datetime.fromtimestamp(timestamp)
        if is_video is None:
            mime, encoding = mimetypes.guess_type('file.' + extension)
            is_video = mime and mime.startswith('video/')
        self._stat = st
        self._is_video = is_video

    @property
    def timestamp(self):
        """The timestamp when this image or video was created."""
        return self._timestamp

    @property
    def title(self):
        """The title of this image. Use this to generate the file name if it is
        set."""
        return self._title or time.strftime(self.DATE_FORMAT,
            self.timestamp.timetuple())

    @property
    def extension(self):
        """The lower case file extension of this image."""
        return self._extension

    @property
    def is_video(self):
        """Whether this image is a video."""
        return self._is_video

    @property
    def stat(self):
        """The ``stat`` result for this image."""
        return self._stat

    def open(self, flags):
        """Opens a readable stream to the file.

        :param int flags: Flags passed by *FUSE*.

        :return: an object supporting ``seek(offset)`` and ``read(size)`` from
            :class:`file`
        """
        raise NotImplementedError()


class FileBasedImage(Image):
    """An image or video.
    """

    def __init__(self, title, location, timestamp, is_video = None):
        """Initialises a file based image.

        :param str title: The title of the image. This should be used to
            generate the file name. If ``title`` is empty or ``None``,
            ``timestamp`` is used instead.

        :param str location: The location of this image in the file system.

        :param timestamp: The timestamp when this image or video was
            created.
        :type timestamp: int or datetime.datetime

        :param bool is_video: Whether this image is a video. This must be either
            ``True`` or ``False``, or ``None``. If it is ``None``, the type is
            inferred from the file *MIME type*.
        """
        super(FileBasedImage, self).__init__(
            title,
            location.rsplit('.', 1)[-1].lower(),
            timestamp,
            os.lstat(location),
            is_video)
        self._location = location

    @property
    def location(self):
        """The location of this image or video in the file system."""
        return self._location

    @property
    def stat(self):
        """The ``stat`` result for this image."""
        return os.lstat(self.location)

    def open(self, flags):
        return open(self.location, 'rb')
