import unittest,base64
from unittest.mock import patch,MagicMock
import media
class MediaTests(unittest.TestCase):
    @patch('media.client')
    def test_explicit_generation_interfaces(self,c):
        api=c.return_value
        api.images.generate.return_value.data=[MagicMock(b64_json=base64.b64encode(b'png').decode())]
        self.assertEqual(media.image('unused','diagram','configured-image'),b'png')
        api.audio.speech.create.return_value.read.return_value=b'mp3'
        self.assertEqual(media.speech('unused','hello','configured-tts'),b'mp3')
        api.videos.create.return_value.model_dump.return_value={'id':'job','status':'queued'}
        self.assertEqual(media.start_video('unused','concept','configured-video')['status'],'queued')
        api.videos.retrieve.return_value.model_dump.return_value={'id':'job','status':'in_progress'}
        self.assertIsNone(media.poll_video('unused','job')[1]);api.videos.download_content.assert_not_called()
        api.videos.retrieve.return_value.model_dump.return_value={'id':'job','status':'completed'}
        api.videos.download_content.return_value.read.return_value=b'mp4'
        self.assertEqual(media.poll_video('unused','job')[1],b'mp4')
if __name__=='__main__':unittest.main()
