import os
import pickle
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request

def get_authenticated_service_for_content_check(credentials_file, token_pickle_file="content_check_token.pickle"):
    """
    get authenticated youtube service for content id checking
    """
    credentials = None
    
    # scopes for content checking
    scopes = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube"
    ]
    
    # load credentials from token pickle if it exists
    if os.path.exists(token_pickle_file):
        print(f"loading credentials from {token_pickle_file}...")
        with open(token_pickle_file, 'rb') as token:
            credentials = pickle.load(token)
    
    # if credentials don't exist or are invalid, get new ones
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("refreshing access token...")
            credentials.refresh(Request())
        else:
            print(f"fetching new tokens with scopes: {scopes}")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                credentials_file, scopes)
            credentials = flow.run_local_server(port=8080)
        
        # save credentials for next run
        with open(token_pickle_file, 'wb') as token:
            print(f"saving credentials to {token_pickle_file} for future use...")
            pickle.dump(credentials, token)
    
    print(f"successfully authenticated with scopes: {credentials.scopes}")
    
    # build and return youtube api service
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def check_content_id_status(youtube, video_id):
    """
    check contentid claim status for a youtube video
    """
    try:
        print(f"checking content id status for video: {video_id}")
        
        # get video's content details and status
        response = youtube.videos().list(
            part="contentDetails,status",
            id=video_id
        ).execute()
        
        if not response.get('items', []):
            print(f"video {video_id} not found")
            return None
        
        video = response['items'][0]
        
        # check for content id claims
        has_content_id_claim = False
        claim_info = {}
        
        if 'contentDetails' in video:
            content_details = video['contentDetails']
            print("successfully retrieved content details")
            
            if 'licensedContent' in content_details:
                has_content_id_claim = content_details['licensedContent']
                claim_info['licensedContent'] = content_details['licensedContent']
        
            if 'regionRestriction' in content_details:
                claim_info['regionRestriction'] = content_details['regionRestriction']
                
            claim_info['contentDetails'] = content_details
        
        if 'status' in video:
            status = video['status']
            print("successfully retrieved status information")
            
            for status_field in ['uploadStatus', 'privacyStatus', 'license', 'embeddable', 
                               'publicStatsViewable', 'madeForKids']:
                if status_field in status:
                    claim_info[status_field] = status[status_field]
            
            claim_info['status'] = status
        
        if has_content_id_claim:
            print(f"video {video_id} has contentid claims.")
        else:
            print(f"video {video_id} does not appear to have contentid claims.")
        
        return claim_info
        
    except googleapiclient.errors.HttpError as e:
        print(f"an http error occurred: {e}")
        error_content = getattr(e, 'content', b'').decode('utf-8') if hasattr(e, 'content') else 'no detailed error content'
        print(f"error details: {error_content}")
        return None

if __name__ == "__main__":
    # for local testing without https
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    
    client_secret_file = "client_secret.json"
    token_file = "content_check_token.pickle"
    
    print("starting youtube api authentication for content checking...")
    youtube = get_authenticated_service_for_content_check(client_secret_file, token_file)
    
    video_id = "sQzPTgLvfJ0"
    content_id_info = check_content_id_status(youtube, video_id)
    
    if content_id_info:
        print("
content id status information:")
        for key, value in content_id_info.items():
            if key not in ['contentDetails', 'status']:
                print(f"  {key}: {value}")
    else:
        print("failed to retrieve content id information.")