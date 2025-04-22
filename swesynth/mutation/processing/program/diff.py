import unidiff

__all__ = ["swap_a_b_of_patch_and_clean"]


def swap_a_b_of_patch_and_clean(patch: str) -> str:
    r'''
    Input:
diff --git b/.vscode/launch.json a/.vscode/launch.json
index 55d3bc2..ce3a570 100644
--- b/.vscode/launch.json
+++ a/.vscode/launch.json
@@ -64,7 +64,7 @@
             "name": "Main",
             "type": "debugpy",
             "request": "launch",
-            "module": "swesynth.mutation.mutator",
+            "module": "swesynth.scripts.create_dataset",
             "env": {
                 "LANGCHAIN_TRACING_V2": "true",
             },
diff --git b/swesynth/mutation/mutator.py a/swesynth/mutation/mutator.py
index 1d33908..0990482 100644
--- b/swesynth/mutation/mutator.py
+++ a/swesynth/mutation/mutator.py
@@ -42,13 +42,13 @@ class Mutator:
         with get_openai_callback() as cost, \
             Tester(self.source_code).setup() as tester:
 
-            # original_test_status: TestStatus = tester.test()
-            # tester.original_test_status = original_test_status
-            # logger.info(f"Original test status: {original_test_status}")
-            # if not original_test_status:
-            #     logger.error("Failed to test original source code, skip this commit")
-            #     return
-            # # self.strategy.load(tester.test_targeter)
+            original_test_status: TestStatus = tester.test()
+            tester.original_test_status = original_test_status
+            logger.info(f"Original test status: {original_test_status}")
+            if not original_test_status:
+                logger.error("Failed to test original source code, skip this commit")
+                return
+            self.strategy.load(tester.test_targeter)
 
             mutant_count: int = 0
             mutated_repo: RepositorySnapshot
diff --git b/swesynth/mutation/validator/tester.py a/swesynth/mutation/validator/tester.py
index 4ca238b..ec3219b 100644
--- b/swesynth/mutation/validator/tester.py
+++ a/swesynth/mutation/validator/tester.py
@@ -35,7 +35,7 @@ class Tester:
         Initialize needed metadata for testing
         """
         self.docker_manager = DockerManager(self.source_code)
-        # self.test_targeter = DynamicCallGraphTestTargeter(self)
+        self.test_targeter = DynamicCallGraphTestTargeter(self)
     
     def setup(self) -> "Tester":
         self.docker_manager.build_docker_image()

    Output:
--- a/.vscode/launch.json
+++ b/.vscode/launch.json
@@ -64,7 +64,7 @@
             "name": "Main",
             "type": "debugpy",
             "request": "launch",
-            "module": "swesynth.mutation.mutator",
+            "module": "swesynth.scripts.create_dataset",
             "env": {
                 "LANGCHAIN_TRACING_V2": "true",
             },
--- a/swesynth/mutation/mutator.py
+++ b/swesynth/mutation/mutator.py
@@ -42,13 +42,13 @@ class Mutator:
         with get_openai_callback() as cost, \
             Tester(self.source_code).setup() as tester:
 
-            # original_test_status: TestStatus = tester.test()
-            # tester.original_test_status = original_test_status
-            # logger.info(f"Original test status: {original_test_status}")
-            # if not original_test_status:
-            #     logger.error("Failed to test original source code, skip this commit")
-            #     return
-            # # self.strategy.load(tester.test_targeter)
+            original_test_status: TestStatus = tester.test()
+            tester.original_test_status = original_test_status
+            logger.info(f"Original test status: {original_test_status}")
+            if not original_test_status:
+                logger.error("Failed to test original source code, skip this commit")
+                return
+            self.strategy.load(tester.test_targeter)
 
             mutant_count: int = 0
             mutated_repo: RepositorySnapshot
--- a/swesynth/mutation/validator/tester.py
+++ b/swesynth/mutation/validator/tester.py
@@ -35,7 +35,7 @@ class Tester:
         Initialize needed metadata for testing
         """
         self.docker_manager = DockerManager(self.source_code)
-        # self.test_targeter = DynamicCallGraphTestTargeter(self)
+        self.test_targeter = DynamicCallGraphTestTargeter(self)
     
     def setup(self) -> "Tester":
         self.docker_manager.build_docker_image()   
    '''
    patch_set = unidiff.PatchSet(patch)
    file: unidiff.PatchedFile
    for file in patch_set:
        file.patch_info = ""
        if file.source_file.startswith("a/") and file.target_file.startswith("b/"):
            continue
        if file.source_file.startswith("b/") and file.target_file.startswith("a/"):
            file.source_file = file.source_file.replace("b/", "a/", 1)
            file.target_file = file.target_file.replace("a/", "b/", 1)
        else:
            raise ValueError("Invalid file name")
    return str(patch_set)
