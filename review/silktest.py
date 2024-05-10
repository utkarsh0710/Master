import json
import sys
import boto3
import time
from moviepy.editor import VideoFileClip
import argparse
mediaconvert = boto3.client('mediaconvert', region_name='eu-north-1')

# Define the argument parsers
parser = argparse.ArgumentParser(description="Medai transcode command line interface.")
parser.add_argument("--filename", required=True, help="Path to the transcode config JSON file.")
parser.add_argument("--override", action="store_true", help="Override existing transcode video files.")
parser.add_argument("--delta", action="store_true", help="Check the delta of input video transcodes.")
parser.add_argument("--dryrun", action="store_true", help="Print what transcode jobs will run when you submit jobs.")
args = parser.parse_args()


# Function to check existance of file in given s3 bucket
def check_file_exists(bucket, file_key):
    try:
        s3.head_object(Bucket=bucket, Key=file_key)
        print(f"File {file_key} exists in {bucket}.")
        return True
    except s3.exceptions.ClientError as e:
        if int(e.response['Error']['Code']) == 404:
            print(f"File {file_key} does not exist in {bucket}.")
            return False
        else:
            raise

def truncate_video(input_key, output_key, max_duration=5):
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
    truncated_input_key = f'generated/{input_key}'
    truncate_video(input_key, truncated_input_key)

    # Upload the truncated video back to S3 (same bucket)
    with open('truncated_video.mp4', 'rb') as f:
        s3.put_object(Bucket='mediatestbed', Key=output_key, Body=f)

    # Delete temporary files
    video_clip.close()
    truncated_clip.close()

    print("Truncated video uploaded successfully.")
    truncated_input_key = f'generated/{input_key}'
    truncate_video(input_key, truncated_input_key)

with open('config/config_param.json', 'r') as f:
    config_param = json.load(f)
jobs_created = {}

def create_media_job(input_key,codec, framerate, resolution):
        truncated_input_key = f'generated/{input_key}'
        codec_params = config_param.get(codec)

        # Update configs dynamically for job payloads
        with open ("config/"+str(codec_params["filename"]), "r") as f:
                job_payload = json.load(f)
                job_payload['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination'] = codec_params['destination']
                job_payload['OutputGroups'][0]['Outputs'][0]['VideoDescription']['CodecSettings'][codec_params['codec_setting_name']]['FramerateNumerator'] = framerate
                job_payload['OutputGroups'][0]['Outputs'][0]['VideoDescription']['Width'] = resolution[0]
                job_payload['OutputGroups'][0]['Outputs'][0]['VideoDescription']['Height'] = resolution[1]
                job_payload['OutputGroups'][0]['Outputs'][0]['NameModifier']=f'_{resolution[1]}{"i" if resolution == (1280, 1080) else "p"}_{framerate}fps_{codec_params["name"]}'
                job_payload['Inputs'][0]['FileInput']=f's3://mediatestbed/{truncated_input_key}'

        # Start the MediaConvert job with the truncated video for codecs
        job_response = mediaconvert.create_job(
            Role='arn:aws:iam::015360308640:role/service-role/MediaTestBed_MediaConvert',
            Settings=job_payload
        )
        #print(job_response)
        job_id = job_response['Job']['Id']
        jobs_created[codec_params['name']] = job_id
        print(f'MediaConvert Job ID for {resolution} at {framerate} fps ({codec_params["codec"]}): {job_id}\n\n')
    

def transcode_video(input_key, resolutions, video_codecs, s3_output_bucket):
        global config_param, jobs_created
        job_statueses = []
        existing_files=[]
        input_base_name = input_key.rsplit('.', 1)[0]
        
        input_files=len(resolutions)*len(frame_rates)*len(video_codecs)
        # Iterate over resolutions, frame_rates, video_codecs from input json  file.
        for resolution in resolutions:
            for framerate in frame_rates:
                for codecs in video_codecs:
                    if bool(args.override==False):

                        # Create input video file suffix with the resolutions, frame_rates, video_codecs
                        resolution_suffix = f"{resolution[1]}{'i' if resolution == (1280, 1080) else 'p'}"
                        output_extension = 'webm' if codecs['id'] in ['VP8', 'VP9'] else 'mp4'
                        output_file = f"{input_base_name}_{resolution_suffix}_{framerate}fps_{codecs['name']}.{output_extension}"
                        print(f"Checking existence of {output_file} in {s3_output_bucket}")

                        # Check the output s3 bucket if the file is exist or not.
                        if check_file_exists(s3_output_bucket, output_file):
                            print(f"{output_file} already exists")
                            existing_files.append(output_file)

                    if bool(args.delta) == True:
                        continue
                    if bool(args.dryrun) == False:
                        create_media_job(file_key,codecs["id"], framerate, resolution)

                    else:
                        print(f'MediaConvert Job ID for {resolution} at {framerate} fps ({codecs["name"]})\n\n')

                if (args.override == True) or (args.filename == True):
                    for ke,valu in jobs_created.items():
                    # Wait for job completion to get the status of job
                        while True:
                            job_status = mediaconvert.get_job(Id=valu)
                            if job_status['Job']['Status'] == 'COMPLETE':
                                print(f"Transcoding completed successfully for {resolution} at {framerate} fps ({ke}).")
                                job_statueses.append(job_status['Job']['Status'])
                                break
                            elif job_status['Job']['Status'] == 'ERROR':
                                print(f"MediaConvert job failed for {resolution} at {framerate} fps ({ke}): {job_status['Job']['ErrorMessage']}")
                                job_statueses.append(job_status['Job']['Status'])
                                return
                            time.sleep(10)

                        if len(set(job_statueses)) == 1 and list(set(job_statueses))[0] == 'COMPLETE':
                            print(f"Transcoded video for {resolution} at {framerate} fps uploaded successfully. \n")
                        else:
                            print("No output file paths found. MediaConvert job might have failed. \n")
        try:
            s3.upload_file(Filename=args.filename, Bucket=s3_output_bucket, Key="videos_config.json")
            print(f"Config file successfully uploaded {s3_output_bucket}")
        except Exception as e:
            print(f"Failed to upload config file to {s3_output_bucket}: {str(e)}")

        if bool(args.delta)==True:     
            print(f"\n\n DELTA :",(input_files) - len(existing_files))
    

if __name__ == "__main__":
    s3 = boto3.client('s3')

    # Read input json file for video_codecs, resolutions, framerates
    with open(args.filename) as json_data:
        config = json.load(json_data)
        resolutions = [(resolution['width'],resolution['height']) for resolution in config['RESOLUTION_KEY']]
        frame_rates = config['FRAMERATE_KEY']
        video_codecs = config['CODEC_KEY']
        #resolutions = [(320, 240), (640, 480)]
        s3_output_bucket = config['S3BUCKET']['output']
        s3_input_bucket = config['S3BUCKET']['input']
        response = s3.list_objects_v2(Bucket=s3_input_bucket)
        if 'Contents' in response:
            for obj in response['Contents']:
                file_key = obj['Key']
                if not file_key.endswith("/") and file_key.count('/') == 0:
                    print(f"Processing file: {file_key}")

                    # Submit the video transcode jobs 
                    transcode_video(file_key, resolutions, video_codecs, s3_output_bucket)
        else:
            print("No files found in the bucket.")
