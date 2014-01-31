# This file is part of beets.
# Copyright 2013, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Specific, edge-case tests for the MediaFile metadata layer.
"""
import os
import shutil
from datetime import date

import _common
from _common import unittest
import beets.mediafile


class EdgeTest(unittest.TestCase):
    def test_emptylist(self):
        # Some files have an ID3 frame that has a list with no elements.
        # This is very hard to produce, so this is just the first 8192
        # bytes of a file found "in the wild".
        emptylist = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 'emptylist.mp3'))
        genre = emptylist.genre
        self.assertEqual(genre, '')

    def test_release_time_with_space(self):
        # Ensures that release times delimited by spaces are ignored.
        # Amie Street produces such files.
        space_time = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 'space_time.mp3'))
        self.assertEqual(space_time.year, 2009)
        self.assertEqual(space_time.month, 9)
        self.assertEqual(space_time.day, 4)

    def test_release_time_with_t(self):
        # Ensures that release times delimited by Ts are ignored.
        # The iTunes Store produces such files.
        t_time = beets.mediafile.MediaFile(
                                os.path.join(_common.RSRC, 't_time.m4a'))
        self.assertEqual(t_time.year, 1987)
        self.assertEqual(t_time.month, 3)
        self.assertEqual(t_time.day, 31)

    def test_tempo_with_bpm(self):
        # Some files have a string like "128 BPM" in the tempo field
        # rather than just a number.
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'bpm.mp3'))
        self.assertEqual(f.bpm, 128)

    def test_discc_alternate_field(self):
        # Different taggers use different vorbis comments to reflect
        # the disc and disc count fields: ensure that the alternative
        # style works.
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'discc.ogg'))
        self.assertEqual(f.disc, 4)
        self.assertEqual(f.disctotal, 5)

    def test_old_ape_version_bitrate(self):
        f = beets.mediafile.MediaFile(os.path.join(_common.RSRC, 'oldape.ape'))
        self.assertEqual(f.bitrate, 0)


_sc = beets.mediafile._safe_cast
class InvalidValueToleranceTest(unittest.TestCase):

    def test_safe_cast_string_to_int(self):
        self.assertEqual(_sc(int, 'something'), 0)

    def test_safe_cast_int_string_to_int(self):
        self.assertEqual(_sc(int, '20'), 20)

    def test_safe_cast_string_to_bool(self):
        self.assertEqual(_sc(bool, 'whatever'), False)

    def test_safe_cast_intstring_to_bool(self):
        self.assertEqual(_sc(bool, '5'), True)

    def test_safe_cast_string_to_float(self):
        self.assertAlmostEqual(_sc(float, '1.234'), 1.234)

    def test_safe_cast_int_to_float(self):
        self.assertAlmostEqual(_sc(float, 2), 2.0)

    def test_safe_cast_string_with_cruft_to_float(self):
        self.assertAlmostEqual(_sc(float, '1.234stuff'), 1.234)

    def test_safe_cast_negative_string_to_float(self):
        self.assertAlmostEqual(_sc(float, '-1.234'), -1.234)

    def test_safe_cast_special_chars_to_unicode(self):
        us = _sc(unicode, 'caf\xc3\xa9')
        self.assertTrue(isinstance(us, unicode))
        self.assertTrue(us.startswith(u'caf'))


class SafetyTest(unittest.TestCase):
    def _exccheck(self, fn, exc, data=''):
        fn = os.path.join(_common.RSRC, fn)
        with open(fn, 'w') as f:
            f.write(data)
        try:
            self.assertRaises(exc, beets.mediafile.MediaFile, fn)
        finally:
            os.unlink(fn) # delete the temporary file

    def test_corrupt_mp3_raises_unreadablefileerror(self):
        # Make sure we catch Mutagen reading errors appropriately.
        self._exccheck('corrupt.mp3', beets.mediafile.UnreadableFileError)

    def test_corrupt_mp4_raises_unreadablefileerror(self):
        self._exccheck('corrupt.m4a', beets.mediafile.UnreadableFileError)

    def test_corrupt_flac_raises_unreadablefileerror(self):
        self._exccheck('corrupt.flac', beets.mediafile.UnreadableFileError)

    def test_corrupt_ogg_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ogg', beets.mediafile.UnreadableFileError)

    def test_invalid_ogg_header_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ogg', beets.mediafile.UnreadableFileError,
                       'OggS\x01vorbis')

    def test_corrupt_monkeys_raises_unreadablefileerror(self):
        self._exccheck('corrupt.ape', beets.mediafile.UnreadableFileError)

    def test_invalid_extension_raises_filetypeerror(self):
        self._exccheck('something.unknown', beets.mediafile.FileTypeError)

    def test_magic_xml_raises_unreadablefileerror(self):
        self._exccheck('nothing.xml', beets.mediafile.UnreadableFileError,
                       "ftyp")

    def test_broken_symlink(self):
        fn = os.path.join(_common.RSRC, 'brokenlink')
        os.symlink('does_not_exist', fn)
        try:
            self.assertRaises(IOError,
                              beets.mediafile.MediaFile, fn)
        finally:
            os.unlink(fn)


class SideEffectsTest(unittest.TestCase):
    def setUp(self):
        self.empty = os.path.join(_common.RSRC, 'empty.mp3')

    def test_opening_tagless_file_leaves_untouched(self):
        old_mtime = os.stat(self.empty).st_mtime
        beets.mediafile.MediaFile(self.empty)
        new_mtime = os.stat(self.empty).st_mtime
        self.assertEqual(old_mtime, new_mtime)


class EncodingTest(unittest.TestCase):
    def setUp(self):
        src = os.path.join(_common.RSRC, 'full.m4a')
        self.path = os.path.join(_common.RSRC, 'test.m4a')
        shutil.copy(src, self.path)

        self.mf = beets.mediafile.MediaFile(self.path)

    def tearDown(self):
        os.remove(self.path)

    def test_unicode_label_in_m4a(self):
        self.mf.label = u'foo\xe8bar'
        self.mf.save()
        new_mf = beets.mediafile.MediaFile(self.path)
        self.assertEqual(new_mf.label, u'foo\xe8bar')


class ZeroLengthMediaFile(beets.mediafile.MediaFile):
    @property
    def length(self):
        return 0.0


class MissingAudioDataTest(unittest.TestCase):
    def setUp(self):
        super(MissingAudioDataTest, self).setUp()
        path = os.path.join(_common.RSRC, 'full.mp3')
        self.mf = ZeroLengthMediaFile(path)

    def test_bitrate_with_zero_length(self):
        del self.mf.mgfile.info.bitrate # Not available directly.
        self.assertEqual(self.mf.bitrate, 0)


class TypeTest(unittest.TestCase):
    def setUp(self):
        super(TypeTest, self).setUp()
        path = os.path.join(_common.RSRC, 'full.mp3')
        self.mf = beets.mediafile.MediaFile(path)

    def test_year_integer_in_string(self):
        self.mf.year = '2009'
        self.assertEqual(self.mf.year, 2009)

    def test_set_replaygain_gain_to_none(self):
        self.mf.rg_track_gain = None
        self.assertEqual(self.mf.rg_track_gain, 0.0)

    def test_set_replaygain_peak_to_none(self):
        self.mf.rg_track_peak = None
        self.assertEqual(self.mf.rg_track_peak, 0.0)

    def test_set_year_to_none(self):
        self.mf.year = None
        self.assertEqual(self.mf.year, 0)

    def test_set_track_to_none(self):
        self.mf.track = None
        self.assertEqual(self.mf.track, 0)


class SoundCheckTest(unittest.TestCase):
    def test_round_trip(self):
        data = beets.mediafile._sc_encode(1.0, 1.0)
        gain, peak = beets.mediafile._sc_decode(data)
        self.assertEqual(gain, 1.0)
        self.assertEqual(peak, 1.0)

    def test_decode_zero(self):
        data = u' 80000000 80000000 00000000 00000000 00000000 00000000 ' \
               u'00000000 00000000 00000000 00000000'
        gain, peak = beets.mediafile._sc_decode(data)
        self.assertEqual(gain, 0.0)
        self.assertEqual(peak, 0.0)

    def test_malformatted(self):
        gain, peak = beets.mediafile._sc_decode(u'foo')
        self.assertEqual(gain, 0.0)
        self.assertEqual(peak, 0.0)


class ID3v23Test(unittest.TestCase):
    def _make_test(self, ext='mp3'):
        src = os.path.join(_common.RSRC, 'full.{0}'.format(ext))
        self.path = os.path.join(_common.RSRC, 'test.{0}'.format(ext))
        shutil.copy(src, self.path)
        return beets.mediafile.MediaFile(self.path)

    def _delete_test(self):
        os.remove(self.path)

    def test_v24_year_tag(self):
        mf = self._make_test()
        try:
            mf.year = 2013
            mf.save(id3v23=False)
            frame = mf.mgfile['TDRC']
            self.assertTrue('2013' in str(frame))
            self.assertTrue('TYER' not in mf.mgfile)
        finally:
            self._delete_test()

    def test_v23_year_tag(self):
        mf = self._make_test()
        try:
            mf.year = 2013
            mf.save(id3v23=True)
            frame = mf.mgfile['TYER']
            self.assertTrue('2013' in str(frame))
            self.assertTrue('TDRC' not in mf.mgfile)
        finally:
            self._delete_test()

    def test_v23_on_non_mp3_is_noop(self):
        mf = self._make_test('m4a')
        try:
            mf.year = 2013
            mf.save(id3v23=True)
        finally:
            self._delete_test()


class ReadWriteTest(unittest.TestCase):
    """Test writing and reading tags
    """

    extensions = ['mp3', 'm4a', 'alac.m4a', 'mpc',
            'flac', 'ape', 'ogg', 'wma', 'wv']

    def test_read_common(self):
        for ext in self.extensions:
            mediafile = full_mediafile_fixture(ext)
            self.assertEqual(mediafile.title, 'full')
            self.assertEqual(mediafile.album, 'the album')
            self.assertEqual(mediafile.artist, 'the artist')
            self.assertEqual(mediafile.year, 2001)
            self.assertEqual(mediafile.track, 2)
            self.assertEqual(mediafile.tracktotal, 3)
            self.assertEqual(mediafile.comp, True)
            self.assertEqual(mediafile.lyrics, 'the lyrics')
            self.assertEqual(mediafile.rg_track_gain, 0.0)

    def test_empty_write_common(self):
        """Set tags on files which do not have tags yet
        """
        for ext in self.extensions:
            mediafile = empty_mediafile_fixture(ext)

            mediafile.title = 'empty'
            mediafile.album = 'another album'
            mediafile.artist = 'another artist'
            mediafile.year = 2002
            mediafile.track = 3
            mediafile.tracktotal = 4
            mediafile.comp = False
            mediafile.catalognum = 'CD1'
            mediafile.rg_track_gain = 1.0
            mediafile.rg_track_peak = -1.0
            mediafile.save()

            mediafile = beets.mediafile.MediaFile(mediafile.path)
            self.assertEqual(mediafile.title, 'empty')
            self.assertEqual(mediafile.album, 'another album')
            self.assertEqual(mediafile.artist, 'another artist')
            self.assertEqual(mediafile.year, 2002)
            self.assertEqual(mediafile.track, 3)
            self.assertEqual(mediafile.tracktotal, 4)
            self.assertEqual(mediafile.comp, False)
            self.assertEqual(mediafile.catalognum, 'CD1')
            self.assertEqual(mediafile.rg_track_gain, 1.0)
            self.assertEqual(mediafile.rg_track_peak, -1.0)
    def test_overwrite_common(self):
        for ext in self.extensions:
            mediafile = full_mediafile_fixture(ext)

            # Make sure the tags are already set when writing a second time
            for i in range(2):
                mediafile.title = 'empty'
                mediafile.album = 'another album'
                mediafile.artist = 'another artist'
                mediafile.year = 2002
                mediafile.track = 3
                mediafile.tracktotal = 4
                mediafile.comp = False
                mediafile.catalognum = 'CD1'
                mediafile.rg_track_gain = 1.0
                mediafile.rg_track_peak = -1.0
                mediafile.save()
                mediafile = beets.mediafile.MediaFile(mediafile.path)

            self.assertEqual(mediafile.title, 'empty')
            self.assertEqual(mediafile.album, 'another album')
            self.assertEqual(mediafile.artist, 'another artist')
            self.assertEqual(mediafile.year, 2002)
            self.assertEqual(mediafile.track, 3)
            self.assertEqual(mediafile.tracktotal, 4)
            self.assertEqual(mediafile.comp, False)
            self.assertEqual(mediafile.catalognum, 'CD1')
            self.assertEqual(mediafile.rg_track_gain, 1.0)
            self.assertEqual(mediafile.rg_track_peak, -1.0)

    def test_read_write_full_dates(self):
        for ext in self.extensions:
            mediafile = full_mediafile_fixture(ext)
            mediafile.year = 2001
            mediafile.month = 1
            mediafile.day = 2
            mediafile.original_year = 1999
            mediafile.original_month = 12
            mediafile.original_day = 30
            mediafile.save()

            mediafile = beets.mediafile.MediaFile(mediafile.path)
            self.assertEqual(mediafile.year, 2001)
            self.assertEqual(mediafile.month, 1)
            self.assertEqual(mediafile.day, 2)
            self.assertEqual(mediafile.date, date(2001,1,2))
            self.assertEqual(mediafile.original_year, 1999)
            self.assertEqual(mediafile.original_month, 12)
            self.assertEqual(mediafile.original_day, 30)
            self.assertEqual(mediafile.original_date, date(1999,12,30))

    def test_read_write_float_none(self):
        for ext in self.extensions:
            mediafile = full_mediafile_fixture(ext)
            mediafile.rg_track_gain = None
            mediafile.rg_track_peak = None
            mediafile.original_year = None
            mediafile.original_month = None
            mediafile.original_day = None
            mediafile.save()

            mediafile = beets.mediafile.MediaFile(mediafile.path)
            self.assertEqual(mediafile.rg_track_gain, 0)
            self.assertEqual(mediafile.rg_track_peak, 0)
            self.assertEqual(mediafile.original_year, 0)
            self.assertEqual(mediafile.original_month, 0)
            self.assertEqual(mediafile.original_day, 0)

    def test_read_write_mb_ids(self):
        for ext in self.extensions:
            mediafile = full_mediafile_fixture(ext)
            mediafile.mb_trackid = 'the-id'
            mediafile.mb_albumid = 'the-id'
            mediafile.mb_artistid = 'the-id'
            mediafile.mb_albumartistid = 'the-id'
            mediafile.mb_releasegroupid = 'the-id'
            mediafile.save()

            mediafile = beets.mediafile.MediaFile(mediafile.path)
            self.assertEqual(mediafile.mb_trackid, 'the-id')
            self.assertEqual(mediafile.mb_albumid, 'the-id')
            self.assertEqual(mediafile.mb_artistid, 'the-id')
            self.assertEqual(mediafile.mb_albumartistid, 'the-id')
            self.assertEqual(mediafile.mb_releasegroupid, 'the-id')


def full_mediafile_fixture(ext):
    """Returns a Mediafile with a lot of tags already set.
    """
    src = os.path.join(_common.RSRC, 'full.{0}'.format(ext))
    path = os.path.join(_common.RSRC, 'test.{0}'.format(ext))
    shutil.copy(src, path)
    return beets.mediafile.MediaFile(path)

def empty_mediafile_fixture(ext):
    """Returns a Mediafile with no tags set.
    """
    src = os.path.join(_common.RSRC, 'empty.{0}'.format(ext))
    path = os.path.join(_common.RSRC, 'test_empty.{0}'.format(ext))
    shutil.copy(src, path)
    return beets.mediafile.MediaFile(path)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
