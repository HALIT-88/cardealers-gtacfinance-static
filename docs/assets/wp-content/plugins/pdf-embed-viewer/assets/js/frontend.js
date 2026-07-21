
// ============custom data tabs===========
jQuery(document).ready(function ($) {
    $('[data-tab-target]:first').addClass('active');
    $('[data-tab-content]:first').addClass('active');
    $('[data-tab-target]').click(function () {
    var target = $(this).data('tab-target');
    $('[data-tab-content]').removeClass('active');
    $('.tab').removeClass('active');
    $(this).addClass('active');
    $(target).addClass('active');
    
  });
});


(function($) {
  // This is the click event for the download button counter
  $(document).on('click','.download-btn',function(e){
    var post_id = $(this).data('post-id');
    var $button = $(this);
    $.ajax({
        url: pdfevFronend.ajaxurl,
        type: 'POST',
        data: {
          action: 'pdfev_count_manager_download',
          ajaxnonce: pdfevFronend.ajaxnonce,
          post_id: post_id,
        },
        success: function(response) {
          if (response.success) {
            $button.find('.pdfev-download-counter').html(response.data.download_count); 
          } else {
            $button.find('.pdfev-download-counter').html('Error: ' + response.data.download_count); 
          }
      },
      error: function(xhr, status, error) {
          console.log('Error:', error);
      }
    });
  });
  // enable 3D flipbook===========
  $('.pdfev-show-flipbook').on('click', function (e) {
    e.preventDefault();

    var $parent = $(this).closest('.pdfev-display-switcher');
    
    $(this).addClass('active');
    $parent.find('.pdfev-show-traditional').removeClass('active');
    
    $parent.find('.pdfev-3dbook-container').show();
    $parent.find('.pdfev-traditional-container').hide();
    initializeFlipbook();
  });

  $('.pdfev-show-traditional').on('click', function (e) {
    e.preventDefault();
    var $parent = $(this).closest('.pdfev-display-switcher');
    $(this).addClass('active');
    $parent.find('.pdfev-show-flipbook').removeClass('active');
    
    $parent.find('.pdfev-traditional-container').show();
    $parent.find('.pdfev-3dbook-container').hide();
  });

  // ===initialize the flipbook===
  $(document).ready(function(){
    initializeFlipbook();
  });
  
  function initializeFlipbook() {
      $('.pdfev-3dbook-viewer').each(function () {
      let $viewer = $(this);
      let post_id = $viewer.data('id');
      let pdfURL = $viewer.data('pdfev-url');

      if (!pdfURL) return;

      let options = {
        pdf: pdfURL,
        page: 1, // or customize per book
        template: function () {
          return {
            html: [
              {
                url: pdfevFronend.pdfevurl + "vendor/3dflipbook/templates/default-book-view.html",
                data: jsData.urls["templates/default-book-view.html"],
              },
            ],
            script: [
              {
                url: pdfevFronend.pdfevurl + "vendor/3dflipbook/js/default-book-view.js",
                data: jsData.urls["js/default-book-view.js"],
              },
            ],
            styles: [
              {
                url: pdfevFronend.pdfevurl + "vendor/3dflipbook/css/font-awesome.min.css",
                data: jsData.urls["css/font-awesome.min.css"],
              },
              {
                url: pdfevFronend.pdfevurl + "vendor/3dflipbook/css/short-black-book-view.css",
                data: jsData.urls["css/short-black-book-view.css"],
              },
            ],
            sounds: {
              startFlip: pdfevFronend.pdfevurl + "vendor/3dflipbook/sounds/start-flip.mp3",
              endFlip: pdfevFronend.pdfevurl + "vendor/3dflipbook/sounds/end-flip.mp3",
            },
            init: undefined,
          };
        },
      };

      $viewer.FlipBook(options);
    });
  }


})(jQuery);
// ============metabox scripts========
