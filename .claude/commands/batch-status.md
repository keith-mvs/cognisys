Check the status of the current CogniSys batch processing job.

Steps:
1. Check for running PowerShell batch processes
2. Count processed documents in `C:\Users\kjfle\ml_batch_results`
3. Read the most recent `batch_results.json` file
4. Display:
   - Total files in batch
   - Successfully processed
   - Failed
   - Success rate
   - Processing speed (files/minute)
   - Estimated time remaining
5. Show top 5 document types classified
6. List any recurring error patterns

Format as a real-time dashboard with progress indicators.
