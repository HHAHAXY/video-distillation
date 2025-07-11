import os
import pickle
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http
from google.auth.transport.requests import Request

def get_authenticated_service(credentials_file, token_pickle_file="token.pickle"):
    """get authenticated youtube service object"""
    credentials = None
    scopes = ["https://www.googleapis.com/auth/youtube.upload", 
              "https://www.googleapis.com/auth/youtube.readonly", 
              "https://www.googleapis.com/auth/youtube.force-ssl"]
    
    if os.path.exists(token_pickle_file):
        print("loading credentials from file...")
        with open(token_pickle_file, 'rb') as token:
            credentials = pickle.load(token)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("refreshing access token...")
            credentials.refresh(Request())
        else:
            print("fetching new tokens...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                credentials_file, scopes)
            credentials = flow.run_local_server(port=8080)
        
        with open(token_pickle_file, 'wb') as token:
            print("saving credentials for future use...")
            pickle.dump(credentials, token)
    
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def upload_video_to_youtube(
    credentials_file,
    video_file,
    title,
    description="",
    tags=None,
    category_id="22",
    privacy_status="private",
    token_pickle_file="token.pickle"
):
    """upload video to youtube"""
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    
    youtube = get_authenticated_service(credentials_file, token_pickle_file)
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
        }
    }
    
    media_file = googleapiclient.http.MediaFileUpload(
        video_file,
        chunksize=1024*1024,
        resumable=True
    )
    
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media_file
    )
    
    print(f"uploading file: {video_file}...")
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"uploaded {int(status.progress() * 100)}%")
    
    print(f"upload complete! video id: {response['id']}")
    return response['id']

if __name__ == "__main__":
    video_id = upload_video_to_youtube(
        credentials_file="client_secret.json",
        video_file="/Users/rusiq/Downloads/youtube_dl/katka1.mp4",
        title="test",
        description="test",
        tags=["test"],
        privacy_status="private"
    )
    print(f"video uploaded successfully! video id: {video_id}")