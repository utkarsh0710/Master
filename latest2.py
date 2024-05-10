import boto3
import time
from moviepy.editor import VideoFileClip

def truncate_video(input_key, output_key, max_duration=5):
    s3 = boto3.client('s3')

    # Download video file from S3
    s3.download_file('mediatestbed', input_key, 'temp_video.mp4')

    # Read video using moviepy
    video_clip = VideoFileClip('temp_video.mp4')

    # Truncate the video to desired length
    truncated_clip = video_clip.subclip(0, min(video_clip.duration, max_duration))

    # Write truncated video to a new file
    truncated_clip.write_videofile('truncated_video.mp4', codec="libx264")

    # Ensure the file is stored inside the 'mediatestbed/generated' folder with the source file name unchanged
    output_folder = 'generated/'
    output_key = output_folder + input_key  # Use the input file name directly

    # Upload the truncated video back to S3 (same bucket)
    with open('truncated_video.mp4', 'rb') as f:
        s3.put_object(Bucket='mediatestbed', Key=output_key, Body=f)

    # Delete temporary files
    video_clip.close()
    truncated_clip.close()

    print("Truncated video uploaded successfully.")

def transcode_video(input_key, resolutions):
    mediaconvert = boto3.client('mediaconvert', region_name='eu-north-1')
    s3 = boto3.client('s3')

    # Truncate the original video to 5 seconds
    truncated_input_key = f'generated/{input_key}'
    truncate_video(input_key, truncated_input_key)

    # Iterate over resolutions
    for resolution in resolutions:
        for framerate in [30, 60]:
            # Start the MediaConvert job with the truncated video for AV1 codec
            job_response_av1 = mediaconvert.create_job(
                Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                Settings={
                    'OutputGroups': [
                        {
                            'Name': 'File Group AV1',
                            'OutputGroupSettings': {
                                'Type': 'FILE_GROUP_SETTINGS',
                                'FileGroupSettings': {
                                    'Destination': 's3://mediatestbed-output/'
                                }
                            },
                            'Outputs': [
                                {
                                    'ContainerSettings': {
                                        'Container': 'MP4',
                                        'Mp4Settings': {
                                            'CslgAtom': 'INCLUDE',
                                            'CttsVersion': 0,
                                            'FreeSpaceBox': 'EXCLUDE',
                                            'MoovPlacement': 'PROGRESSIVE_DOWNLOAD'
                                        }
                                    },
                                    'Extension': '.mp4',
                                    'VideoDescription': {
                                        'ScalingBehavior': 'DEFAULT',
                                        'TimecodeInsertion': 'DISABLED',
                                        'AntiAlias': 'ENABLED',
                                        'Sharpness': 50,
                                        'CodecSettings': {
                                            'Codec': 'AV1',
                                            'Av1Settings': {
                                                'AdaptiveQuantization': 'HIGH',
                                                'FramerateControl': 'SPECIFIED',
                                                'FramerateConversionAlgorithm': 'DUPLICATE_DROP',
                                                'FramerateDenominator': 1,
                                                'FramerateNumerator': framerate,
                                                'GopSize': 90,
                                                'RateControlMode': 'QVBR',
                                                'SpatialAdaptiveQuantization': 'ENABLED',
                                                'MaxBitrate': 6000000  # Added maxBitrate property
                                            }
                                        },
                                        'AfdSignaling': 'NONE',
                                        'DropFrameTimecode': 'ENABLED',
                                        'RespondToAfd': 'NONE',
                                        'ColorMetadata': 'INSERT',
                                        'Width': resolution[0],  # Added width
                                        'Height': resolution[1],  # Added height
                                    },
                                    'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_av1'
                                }
                            ]
                        }
                    ],
                    'AdAvailOffset': 0,
                    'Inputs': [
                        {
                            'AudioSelectors': {
                                'Audio Selector 1': {
                                    'Offset': 0,
                                    'DefaultSelection': 'DEFAULT'
                                }
                            },
                            'VideoSelector': {
                                'ColorSpace': 'FOLLOW',
                                'Rotate': 'DEGREE_0'
                            },
                            'FilterEnable': 'AUTO',
                            'PsiControl': 'USE_PSI',
                            'FilterStrength': 0,
                            'DeblockFilter': 'DISABLED',
                            'DenoiseFilter': 'DISABLED',
                            'TimecodeSource': 'EMBEDDED',
                            'FileInput': f's3://mediatestbed/{truncated_input_key}'
                        }
                    ]
                }
            )

            job_id_av1 = job_response_av1['Job']['Id']
            print(f"MediaConvert Job ID for {resolution} at {framerate} fps (AV1): {job_id_av1}")

            # Start the MediaConvert job with the truncated video for H.264 codec
            job_response_h264 = mediaconvert.create_job(
                Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                Settings={
                    'OutputGroups': [
                        {
                            'Name': 'File Group H264',
                            'OutputGroupSettings': {
                                'Type': 'FILE_GROUP_SETTINGS',
                                'FileGroupSettings': {
                                    'Destination': 's3://mediatestbed-output/'
                                }
                            },
                            'Outputs': [
                                {
                                    'ContainerSettings': {
                                        'Container': 'MP4',
                                        'Mp4Settings': {
                                            'CslgAtom': 'INCLUDE',
                                            'CttsVersion': 0,
                                            'FreeSpaceBox': 'EXCLUDE',
                                            'MoovPlacement': 'PROGRESSIVE_DOWNLOAD'
                                        }
                                    },
                                    'Extension': '.mp4',
                                    'VideoDescription': {
                                        'ScalingBehavior': 'DEFAULT',
                                        'TimecodeInsertion': 'DISABLED',
                                        'AntiAlias': 'ENABLED',
                                        'Sharpness': 50,
                                        'CodecSettings': {
                                            'Codec': 'H_264',
                                            'H264Settings': {
                                                "AdaptiveQuantization": "HIGH",
                                                "CodecLevel": "AUTO",
                                                "CodecProfile": "MAIN",
                                                "DynamicSubGop": "STATIC",
                                                "EntropyEncoding": "CABAC",
                                                "FieldEncoding": "PAFF",
                                                "FlickerAdaptiveQuantization": "DISABLED",
                                                "FramerateDenominator": 1,
                                                "FramerateNumerator": framerate,
                                                "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                                "GopBReference": "DISABLED",
                                                "GopClosedCadence": 0,
                                                "GopSize": 90,
                                                "GopSizeUnits": "FRAMES",
                                                "InterlaceMode": "PROGRESSIVE",
                                                "MaxBitrate": 5000000,
                                                "MinIInterval": 0,
                                                "NumberBFramesBetweenReferenceFrames": 2,
                                                "NumberReferenceFrames": 3,
                                                "ParControl": "INITIALIZE_FROM_SOURCE",
                                                "QualityTuningLevel": "SINGLE_PASS",
                                                "RateControlMode": "QVBR",
                                                "RepeatPps": "DISABLED",
                                                "SceneChangeDetect": "ENABLED",
                                                "Slices": 1,
                                                "SlowPal": "DISABLED",
                                                "Softness": 0,
                                                "SpatialAdaptiveQuantization": "ENABLED",
                                                "Syntax": "DEFAULT",
                                                "Telecine": "NONE",
                                                "TemporalAdaptiveQuantization": "ENABLED",
                                                "UnregisteredSeiTimecode": "DISABLED"
                                            }
                                        },
                                        'AfdSignaling': 'NONE',
                                        'DropFrameTimecode': 'ENABLED',
                                        'RespondToAfd': 'NONE',
                                        'ColorMetadata': 'INSERT',
                                        'Width': resolution[0],  # Added width
                                        'Height': resolution[1],  # Added height
                                    },
                                    'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_h264'
                                }
                            ]
                        }
                    ],
                    'AdAvailOffset': 0,
                    'Inputs': [
                        {
                            'AudioSelectors': {
                                'Audio Selector 1': {
                                    'Offset': 0,
                                    'DefaultSelection': 'DEFAULT'
                                }
                            },
                            'VideoSelector': {
                                'ColorSpace': 'FOLLOW',
                                'Rotate': 'DEGREE_0'
                            },
                            'FilterEnable': 'AUTO',
                            'PsiControl': 'USE_PSI',
                            'FilterStrength': 0,
                            'DeblockFilter': 'DISABLED',
                            'DenoiseFilter': 'DISABLED',
                            'TimecodeSource': 'EMBEDDED',
                            'FileInput': f's3://mediatestbed/{truncated_input_key}'
                        }
                    ]
                }
            )

            job_id_h264 = job_response_h264['Job']['Id']
            print(f"MediaConvert Job ID for {resolution} at {framerate} fps (H.264): {job_id_h264}")

            # Start the MediaConvert job with the truncated video for H.265 codec
            job_response_h265 = mediaconvert.create_job(
                Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                Settings={
                    'OutputGroups': [
                        {
                            'Name': 'File Group H265',
                            'OutputGroupSettings': {
                                'Type': 'FILE_GROUP_SETTINGS',
                                'FileGroupSettings': {
                                    'Destination': 's3://mediatestbed-output/'
                                }
                            },
                            'Outputs': [
                                {
                                    'ContainerSettings': {
                                        'Container': 'MP4',
                                        'Mp4Settings': {
                                            'CslgAtom': 'INCLUDE',
                                            'CttsVersion': 0,
                                            'FreeSpaceBox': 'EXCLUDE',
                                            'MoovPlacement': 'PROGRESSIVE_DOWNLOAD'
                                        }
                                    },
                                    'Extension': '.mp4',
                                    'VideoDescription': {
                                        'ScalingBehavior': 'DEFAULT',
                                        'TimecodeInsertion': 'DISABLED',
                                        'AntiAlias': 'ENABLED',
                                        'Sharpness': 50,
                                        'CodecSettings': {
                                            'Codec': 'H_265',
                                            'H265Settings': {
                                                'AdaptiveQuantization': 'HIGH',
                                                'CodecLevel': 'AUTO',
                                                'CodecProfile': 'MAIN_MAIN',
                                                'DynamicSubGop': 'STATIC',
                                                'FlickerAdaptiveQuantization': 'DISABLED',
                                                'FramerateConversionAlgorithm': 'DUPLICATE_DROP',
                                                'FramerateDenominator': 1,
                                                'FramerateNumerator': framerate,
                                                'GopBReference': 'DISABLED',
                                                'GopClosedCadence': 0,
                                                'GopSize': 90,
                                                'GopSizeUnits': 'FRAMES',
                                                'InterlaceMode': 'PROGRESSIVE',
                                                'MaxBitrate': 5000000,
                                                'MinIInterval': 0,
                                                'NumberBFramesBetweenReferenceFrames': 2,
                                                'NumberReferenceFrames': 3,
                                                'ParControl': 'INITIALIZE_FROM_SOURCE',
                                                'QualityTuningLevel': 'SINGLE_PASS',
                                                'RateControlMode': 'QVBR',
                                                'QvbrSettings': {
                                                    'QvbrQualityLevel': 1
                                                },
                                                'SampleAdaptiveOffsetFilterMode': 'DEFAULT',
                                                'SceneChangeDetect': 'ENABLED',
                                                'Slices': 1,
                                                'SlowPal': 'DISABLED',
                                                'SpatialAdaptiveQuantization': 'ENABLED',
                                                'Telecine': 'NONE',
                                                'TemporalAdaptiveQuantization': 'ENABLED',
                                                'UnregisteredSeiTimecode': 'DISABLED',
                                            }
                                        },
                                        'AfdSignaling': 'NONE',
                                        'DropFrameTimecode': 'ENABLED',
                                        'RespondToAfd': 'NONE',
                                        'ColorMetadata': 'INSERT',
                                        'Width': resolution[0],  # Added width
                                        'Height': resolution[1],  # Added height
                                    },
                                    'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_h265'
                                }
                            ]
                        }
                    ],
                    'AdAvailOffset': 0,
                    'Inputs': [
                        {
                            'AudioSelectors': {
                                'Audio Selector 1': {
                                    'Offset': 0,
                                    'DefaultSelection': 'DEFAULT'
                                }
                            },
                            'VideoSelector': {
                                'ColorSpace': 'FOLLOW',
                                'Rotate': 'DEGREE_0'
                            },
                            'FilterEnable': 'AUTO',
                            'PsiControl': 'USE_PSI',
                            'FilterStrength': 0,
                            'DeblockFilter': 'DISABLED',
                            'DenoiseFilter': 'DISABLED',
                            'TimecodeSource': 'EMBEDDED',
                            'FileInput': f's3://mediatestbed/{truncated_input_key}'
                        }
                    ]
                }
            )

            job_id_h265 = job_response_h265['Job']['Id']
            print(f"MediaConvert Job ID for {resolution} at {framerate} fps (H.265): {job_id_h265}")
            

            
            # Start the MediaConvert job with the truncated video for MPEG-2 codec
            if resolution in [(320, 240), (640, 480), (1280, 720)]:
              job_response_mpeg2 = mediaconvert.create_job(
                  Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                  Settings={
                      'OutputGroups': [
                          {
                              'Name': 'File Group MPEG2',
                              'OutputGroupSettings': {
                                  'Type': 'FILE_GROUP_SETTINGS',
                                  'FileGroupSettings': {
                                      'Destination': 's3://mediatestbed-output/'
                                  }
                              },
                              'Outputs': [
                                  {
                                      'ContainerSettings': {
                                          'Container': 'MOV',
                                          'MovSettings': {
                                              'CslgAtom': 'INCLUDE',
                                          }
                                      },
                                      'Extension': '.mov',
                                      'VideoDescription': {
                                          'ScalingBehavior': 'DEFAULT',
                                          'TimecodeInsertion': 'DISABLED',
                                          'AntiAlias': 'ENABLED',
                                          'Sharpness': 50,
                                          'CodecSettings': {
                                              'Codec': 'MPEG2',
                                              'Mpeg2Settings': {
                                                  'AdaptiveQuantization': 'HIGH',
                                                  'Bitrate': 10000000,
                                                  'CodecLevel': 'AUTO',
                                                  'CodecProfile': 'MAIN',
                                                  'DynamicSubGop': 'STATIC',
                                                  'FramerateControl': 'INITIALIZE_FROM_SOURCE',
                                                  'FramerateDenominator': 1,
                                                  'FramerateNumerator': framerate,
                                                  'FramerateConversionAlgorithm': 'DUPLICATE_DROP',
                                                  'GopClosedCadence': 1,
                                                  'GopSize': 90,
                                                  'GopSizeUnits': 'FRAMES',
                                                  'ScanTypeConversionMode': 'INTERLACED',
                                                  'InterlaceMode': 'PROGRESSIVE',
                                                  'QualityTuningLevel': 'SINGLE_PASS',
                                                  'RateControlMode': 'VBR',
                                                  'Syntax': 'DEFAULT',
                                                  'IntraDcPrecision': 'AUTO',
                                                  'SpatialAdaptiveQuantization': 'ENABLED'
                                              }
                                          },
                                          'AfdSignaling': 'NONE',
                                          'DropFrameTimecode': 'ENABLED',
                                          'RespondToAfd': 'NONE',
                                          'ColorMetadata': 'INSERT',
                                          'Width': resolution[0],  # Added width
                                          'Height': resolution[1],  # Added height
                                      },
                                      'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_mpeg2'
                                  }
                              ]
                          }
                      ],
                      'AdAvailOffset': 0,
                      'Inputs': [
                          {
                              'AudioSelectors': {
                                  'Audio Selector 1': {
                                      'Offset': 0,
                                      'DefaultSelection': 'DEFAULT'
                                  }
                              },
                              'VideoSelector': {
                                  'ColorSpace': 'FOLLOW',
                                  'Rotate': 'DEGREE_0'
                              },
                              'FilterEnable': 'AUTO',
                              'PsiControl': 'USE_PSI',
                              'FilterStrength': 0,
                              'DeblockFilter': 'DISABLED',
                              'DenoiseFilter': 'DISABLED',
                              'TimecodeSource': 'EMBEDDED',
                              'FileInput': f's3://mediatestbed/{truncated_input_key}'
                          }
                      ]
                  }
              )

              job_id_mpeg2 = job_response_mpeg2['Job']['Id']
              print(f"MediaConvert Job ID for {resolution} at {framerate} fps (MPEG-2): {job_id_mpeg2}")
              


            # Start the MediaConvert job with the truncated video for VP8 codec
            job_response_vp8 = mediaconvert.create_job(
                Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                Settings={
                    'OutputGroups': [
                        {
                            'Name': 'File Group VP8',
                            'OutputGroupSettings': {
                                'Type': 'FILE_GROUP_SETTINGS',
                                'FileGroupSettings': {
                                    'Destination': 's3://mediatestbed-output/'
                                }
                            },
                            'Outputs': [
                                {
                                    'ContainerSettings': {
                                        'Container': 'WEBM',
                                    },
                                    'Extension': '.webm',
                                    'VideoDescription': {
                                        'ScalingBehavior': 'DEFAULT',
                                        'TimecodeInsertion': 'DISABLED',
                                        'AntiAlias': 'ENABLED',
                                        'Sharpness': 50,
                                        'CodecSettings': {
                                            'Codec': 'VP8',
                                            'Vp8Settings': {
                                                'Bitrate': 10000000,
                                                'FramerateControl': 'INITIALIZE_FROM_SOURCE',
                                                'FramerateDenominator': 1,
                                                'FramerateNumerator': framerate,
                                                'FramerateConversionAlgorithm': 'DUPLICATE_DROP',
                                                'GopSize': 90,
                                                'HrdBufferSize': 5000000,
                                                'RateControlMode': 'VBR'
                                            }
                                        },
                                        'AfdSignaling': 'NONE',
                                        'DropFrameTimecode': 'ENABLED',
                                        'RespondToAfd': 'NONE',
                                        'ColorMetadata': 'INSERT',
                                        'Width': resolution[0],  # Added width
                                        'Height': resolution[1],  # Added height
                                    },
                                    'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_vp8'
                                }
                            ]
                        }
                    ],
                    'AdAvailOffset': 0,
                    'Inputs': [
                        {
                            'AudioSelectors': {
                                'Audio Selector 1': {
                                    'Offset': 0,
                                    'DefaultSelection': 'DEFAULT'
                                }
                            },
                            'VideoSelector': {
                                'ColorSpace': 'FOLLOW',
                                'Rotate': 'DEGREE_0'
                            },
                            'FilterEnable': 'AUTO',
                            'PsiControl': 'USE_PSI',
                            'FilterStrength': 0,
                            'DeblockFilter': 'DISABLED',
                            'DenoiseFilter': 'DISABLED',
                            'TimecodeSource': 'EMBEDDED',
                            'FileInput': f's3://mediatestbed/{truncated_input_key}'
                        }
                    ]
                }
            )

            job_id_vp8 = job_response_vp8['Job']['Id']
            print(f"MediaConvert Job ID for {resolution} at {framerate} fps (VP8): {job_id_vp8}")            

            
            # Start the MediaConvert job with the truncated video for VP9 codec
            job_response_vp9 = mediaconvert.create_job(
                Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
                Settings={
                    'OutputGroups': [
                        {
                            'Name': 'File Group VP9',
                            'OutputGroupSettings': {
                                'Type': 'FILE_GROUP_SETTINGS',
                                'FileGroupSettings': {
                                    'Destination': 's3://mediatestbed-output/'
                                }
                            },
                            'Outputs': [
                                {
                                    'ContainerSettings': {
                                        'Container': 'WEBM',
                                    },
                                    'Extension': '.webm',
                                    'VideoDescription': {
                                        'ScalingBehavior': 'DEFAULT',
                                        'TimecodeInsertion': 'DISABLED',
                                        'AntiAlias': 'ENABLED',
                                        'Sharpness': 50,
                                        'CodecSettings': {
                                            'Codec': 'VP9',
                                            'Vp9Settings': {
                                                'Bitrate': 10000000,
                                                'FramerateControl': 'INITIALIZE_FROM_SOURCE',
                                                'FramerateDenominator': 1,
                                                'FramerateNumerator': framerate,
                                                'FramerateConversionAlgorithm': 'DUPLICATE_DROP',
                                                'GopSize': 90,
                                                'HrdBufferSize': 5000000,
                                                'RateControlMode': 'VBR'
                                            }
                                        },
                                        'AfdSignaling': 'NONE',
                                        'DropFrameTimecode': 'ENABLED',
                                        'RespondToAfd': 'NONE',
                                        'ColorMetadata': 'INSERT',
                                        'Width': resolution[0],  # Added width
                                        'Height': resolution[1],  # Added height
                                    },
                                    'NameModifier': f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_vp9'
                                }
                            ]
                        }
                    ],
                    'AdAvailOffset': 0,
                    'Inputs': [
                        {
                            'AudioSelectors': {
                                'Audio Selector 1': {
                                    'Offset': 0,
                                    'DefaultSelection': 'DEFAULT'
                                }
                            },
                            'VideoSelector': {
                                'ColorSpace': 'FOLLOW',
                                'Rotate': 'DEGREE_0'
                            },
                            'FilterEnable': 'AUTO',
                            'PsiControl': 'USE_PSI',
                            'FilterStrength': 0,
                            'DeblockFilter': 'DISABLED',
                            'DenoiseFilter': 'DISABLED',
                            'TimecodeSource': 'EMBEDDED',
                            'FileInput': f's3://mediatestbed/{truncated_input_key}'
                        }
                    ]
                }
            )

            job_id_vp9 = job_response_vp9['Job']['Id']
            print(f"MediaConvert Job ID for {resolution} at {framerate} fps (VP9): {job_id_vp9}")


            # Wait for AV1 job completion
            while True:
                job_status_av1 = mediaconvert.get_job(Id=job_id_av1)
                if job_status_av1['Job']['Status'] == 'COMPLETE':
                    print(f"Transcoding completed successfully for {resolution} at {framerate} fps (AV1).")
                    break
                elif job_status_av1['Job']['Status'] == 'ERROR':
                    print(f"MediaConvert job failed for {resolution} at {framerate} fps (AV1): {job_status_av1['Job']['ErrorMessage']}")
                    return
                time.sleep(10)

            # Wait for H.264 job completion
            while True:
                job_status_h264 = mediaconvert.get_job(Id=job_id_h264)
                if job_status_h264['Job']['Status'] == 'COMPLETE':
                    print(f"Transcoding completed successfully for {resolution} at {framerate} fps (H.264).")
                    break
                elif job_status_h264['Job']['Status'] == 'ERROR':
                    print(f"MediaConvert job failed for {resolution} at {framerate} fps (H.264): {job_status_h264['Job']['ErrorMessage']}")
                    return
                time.sleep(10)

            # Wait for H.265 job completion
            while True:
                job_status_h265 = mediaconvert.get_job(Id=job_id_h265)
                if job_status_h265['Job']['Status'] == 'COMPLETE':
                    print(f"Transcoding completed successfully for {resolution} at {framerate} fps (H.265).")
                    break
                elif job_status_h265['Job']['Status'] == 'ERROR':
                    print(f"MediaConvert job failed for {resolution} at {framerate} fps (H.265): {job_status_h265['Job']['ErrorMessage']}")
                    return
                time.sleep(10)


            # Wait for MPEG-2 job completion
            if resolution in [(320, 240), (640, 480), (1280, 720)]:  
              while True:
                  job_status_mpeg2 = mediaconvert.get_job(Id=job_id_mpeg2)
                  if job_status_mpeg2['Job']['Status'] == 'COMPLETE':
                      print(f"Transcoding completed successfully for {resolution} at {framerate} fps (MPEG-2).")
                      break
                  elif job_status_mpeg2['Job']['Status'] == 'ERROR':
                      print(f"MediaConvert job failed for {resolution} at {framerate} fps (MPEG-2): {job_status_mpeg2['Job']['ErrorMessage']}")
                      return
                  time.sleep(10)

            # Wait for VP8 job completion
            while True:
                job_status_vp8 = mediaconvert.get_job(Id=job_id_vp8)
                if job_status_vp8['Job']['Status'] == 'COMPLETE':
                    print(f"Transcoding completed successfully for {resolution} at {framerate} fps (VP8).")
                    break
                elif job_status_vp8['Job']['Status'] == 'ERROR':
                    print(f"MediaConvert job failed for {resolution} at {framerate} fps (VP8): {job_status_vp9['Job']['ErrorMessage']}")
                    return
                time.sleep(10)

            # Wait for VP9 job completion
            while True:
                job_status_vp9 = mediaconvert.get_job(Id=job_id_vp9)
                if job_status_vp9['Job']['Status'] == 'COMPLETE':
                    print(f"Transcoding completed successfully for {resolution} at {framerate} fps (VP9).")
                    break
                elif job_status_vp9['Job']['Status'] == 'ERROR':
                    print(f"MediaConvert job failed for {resolution} at {framerate} fps (VP9): {job_status_vp9['Job']['ErrorMessage']}")
                    return
                time.sleep(10)



            # Check if all jobs are complete and print the appropriate message
            if job_status_av1['Job']['Status'] == 'COMPLETE' and job_status_h264['Job']['Status'] == 'COMPLETE' and job_status_h265['Job']['Status'] == 'COMPLETE' and job_status_mpeg2['Job']['Status'] == 'COMPLETE' and job_status_vp8['Job']['Status'] == 'COMPLETE' and  job_status_vp9['Job']['Status'] == 'COMPLETE':
                print(f"Transcoded video for {resolution} at {framerate} fps uploaded successfully.\n\n")
            else:
                print("No output file paths found. MediaConvert job might have failed.")



if __name__ == "__main__":
    s3 = boto3.client('s3')
    bucket = 'mediatestbed'

    # List all objects in the S3 bucket
    response = s3.list_objects_v2(Bucket=bucket)
    if 'Contents' in response:
        for obj in response['Contents']:
            file_key = obj['Key']
            # Ensure the file is not already in the 'generated/' folder to avoid re-processing
            if not file_key.startswith("generated/"):
                print(f"Processing file: {file_key}")
                resolutions = [(320, 240), (640, 480), (1280, 720), (1280, 1080), (1920, 1080), (3840, 2160)]  # Add more resolutions as needed
                transcode_video(file_key, resolutions)
    else:
        print("No files found in the bucket.")
