package com.acooldog.toolbox.update.data;

import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.mockwebserver.Dispatcher;
import okio.Buffer;
import org.junit.Test;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;
import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

public class ApkDownloaderTest {
    @Rule public TemporaryFolder temp = new TemporaryFolder();
    @Test public void wrongRangeOfCorrectLengthFallsBackInsteadOfMergingCorruptChunks() throws Exception {
        byte[] expected = new byte[4 * 1024 * 1024];
        for (int i = 0; i < expected.length; i++) expected[i] = (byte) (i * 31);
        AtomicInteger fullRequests = new AtomicInteger();
        MockWebServer server = new MockWebServer();
        server.setDispatcher(new Dispatcher() {
            @Override public MockResponse dispatch(RecordedRequest request) {
            String range = request.getHeader("Range");
            if (range == null) {
                fullRequests.incrementAndGet();
                return new MockResponse().setBody(new Buffer().write(expected));
            } else if (range.equals("bytes=0-0")) {
                return new MockResponse().setResponseCode(206)
                        .addHeader("Content-Range", "bytes 0-0/" + expected.length)
                        .setBody(new Buffer().write(expected, 0, 1));
            } else {
                // Same byte length, wrong offset: old downloader silently merged this response.
                byte[] corrupt = new byte[expected.length / 4];
                Arrays.fill(corrupt, (byte) 7);
                return new MockResponse().setResponseCode(206)
                        .addHeader("Content-Range", "bytes 1-1048576/" + expected.length)
                        .setBody(new Buffer().write(corrupt));
            }
            }
        });
        server.start();
        try {
            File target = new File(temp.getRoot(), "app.apk");
            new ApkDownloader().download(server.url("/apk").toString(), target, null);
            assertEquals(1, fullRequests.get());
            assertArrayEquals(expected, Files.readAllBytes(target.toPath()));
        } finally { server.shutdown(); }
    }
}
