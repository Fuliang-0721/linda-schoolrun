package com.acooldog.toolbox;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.ListView;
import android.widget.TextView;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.ActionBar;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.widget.SearchView;
import androidx.lifecycle.ViewModelProvider;

import com.acooldog.toolbox.route.domain.model.RouteDefinition;
import com.acooldog.toolbox.route.presentation.LocalRouteActionAdapter;
import com.acooldog.toolbox.route.presentation.RouteListViewModel;
import com.acooldog.toolbox.utils.GoUtils;
import com.acooldog.toolbox.utils.SearchSortUtils;
import com.acooldog.toolbox.utils.ShareUtils;
import com.google.android.material.floatingactionbutton.FloatingActionButton;

import java.util.ArrayList;
import java.util.List;

/**
 * 路线管理：本地路线 + 「云端路线」入口（下载后即为本地路线）。
 */
public class RouteActivity extends BaseActivity {
    private RouteListViewModel viewModel;
    private LocalRouteActionAdapter localRouteAdapter;
    private TextView emptyView;
    private ListView routeListView;
    private FloatingActionButton importButton;
    private String currentQuery = "";

    private final ActivityResultLauncher<String[]> importLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), this::handleImportedRoute);

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_route);

        ActionBar actionBar = getSupportActionBar();
        if (actionBar != null) {
            actionBar.setDisplayHomeAsUpEnabled(true);
        }

        viewModel = new ViewModelProvider(this).get(RouteListViewModel.class);
        localRouteAdapter = new LocalRouteActionAdapter(this, new LocalActions());

        emptyView = findViewById(R.id.route_no_data);
        routeListView = findViewById(R.id.route_list_view);
        importButton = findViewById(R.id.fab_import);
        importButton.setOnClickListener(v -> importLauncher.launch(new String[]{"application/json", "*/*"}));

        // 列表头部：云端路线入口（路线不再随包内置，统一从云端下载）
        View cloudEntry = getLayoutInflater().inflate(R.layout.item_route_cloud_entry, routeListView, false);
        cloudEntry.setOnClickListener(v -> startActivity(new Intent(RouteActivity.this, CloudRouteActivity.class)));
        routeListView.addHeaderView(cloudEntry, null, true);
        // 之前从未 setAdapter，导致路线列表不显示；这里补上
        routeListView.setAdapter(localRouteAdapter);
        SearchView searchView = findViewById(R.id.route_search_view);
        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            @Override
            public boolean onQueryTextSubmit(String query) {
                currentQuery = query == null ? "" : query.trim();
                renderRoutes();
                return true;
            }

            @Override
            public boolean onQueryTextChange(String newText) {
                currentQuery = newText == null ? "" : newText.trim();
                renderRoutes();
                return true;
            }
        });

        observeRoutes();
        renderRoutes();
        refreshRoutes();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshRoutes();
    }

    @Override
    public boolean onSupportNavigateUp() {
        finish();
        return true;
    }

    private void observeRoutes() {
        viewModel.getRoutes().observe(this, routes -> renderRoutes());
    }

    private void renderRoutes() {
        List<RouteDefinition> routes = filterRoutes(viewModel.getRoutes().getValue(), currentQuery);
        localRouteAdapter.submit(routes);
        emptyView.setText(R.string.route_empty_local);
        emptyView.setVisibility(routes.isEmpty() ? View.VISIBLE : View.GONE);
        // 列表里始终保留「云端路线」入口，因此不再整块隐藏
        routeListView.setVisibility(View.VISIBLE);
    }

    private void refreshRoutes() {
        try {
            viewModel.refresh();
        } catch (Exception exception) {
            GoUtils.DisplayToast(this, "读取路线失败");
        }
    }

    private void handleImportedRoute(Uri uri) {
        if (uri == null) {
            return;
        }
        try {
            viewModel.importRoute(uri);
            GoUtils.DisplayToast(this, "路线导入成功");
        } catch (Exception exception) {
            GoUtils.DisplayToast(this, "路线导入失败");
        }
    }

    private void openRouteForSimulation(RouteDefinition routeDefinition) {
        Intent intent = new Intent(this, RouteRunActivity.class);
        intent.putExtra(RouteRunActivity.EXTRA_ROUTE_ID, routeDefinition.getId());
        startActivity(intent);
    }

    private void openRouteForEditing(RouteDefinition routeDefinition) {
        Intent intent = new Intent(this, RouteCreateActivity.class);
        intent.putExtra(RouteCreateActivity.EXTRA_EDIT_ROUTE_ID, routeDefinition.getId());
        startActivity(intent);
    }

    private void confirmDelete(RouteDefinition routeDefinition) {
        new AlertDialog.Builder(this)
                .setTitle(R.string.route_delete_title)
                .setMessage(R.string.route_delete_message)
                .setPositiveButton(R.string.route_item_delete, (dialog, which) -> {
                    try {
                        viewModel.deleteRoute(routeDefinition);
                        GoUtils.DisplayToast(this, getString(R.string.route_delete_success));
                    } catch (Exception exception) {
                        GoUtils.DisplayToast(this, getString(R.string.route_delete_failed));
                    }
                })
                .setNegativeButton(R.string.legal_document_close, null)
                .show();
    }

    private List<RouteDefinition> filterRoutes(@Nullable List<RouteDefinition> routes, @NonNull String query) {
        List<RouteDefinition> filtered = new ArrayList<>();
        if (routes == null) {
            return filtered;
        }
        for (RouteDefinition routeDefinition : routes) {
            if (SearchSortUtils.matches(query, routeDefinition.getName())) {
                filtered.add(routeDefinition);
            }
        }
        return filtered;
    }

    private final class LocalActions implements LocalRouteActionAdapter.Actions {
        @Override
        public void onRun(RouteDefinition routeDefinition) {
            openRouteForSimulation(routeDefinition);
        }

        @Override
        public void onEdit(RouteDefinition routeDefinition) {
            openRouteForEditing(routeDefinition);
        }

        @Override
        public void onShare(RouteDefinition routeDefinition) {
            ShareUtils.shareFile(RouteActivity.this, routeDefinition.getFile(), routeDefinition.getName());
        }

        @Override
        public void onDelete(RouteDefinition routeDefinition) {
            confirmDelete(routeDefinition);
        }
    }
}
